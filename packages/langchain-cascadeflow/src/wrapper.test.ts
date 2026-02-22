import { describe, it, expect, vi } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, HumanMessage, AIMessage, AIMessageChunk } from '@langchain/core/messages';
import { ChatResult, ChatGenerationChunk } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { CascadeFlow } from './wrapper.js';

/**
 * Mock chat model for testing
 */
class MockChatModel extends BaseChatModel {
  modelName: string;
  responses: ChatResult[];
  callCount = 0;
  lastOptions: any;
  lastInvokeOptions: any;

  constructor(modelName: string, responses: ChatResult[] = []) {
    super({});
    this.modelName = modelName;
    this.responses = responses;
  }

  _llmType(): string {
    return 'mock';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    this.lastOptions = options;
    const index = Math.min(this.callCount, this.responses.length - 1);
    const response = this.responses[index];
    this.callCount++;
    if (!response) {
      throw new Error('No mock response configured');
    }
    return response;
  }

  override async invoke(input: any, options?: any): Promise<any> {
    this.lastInvokeOptions = options;
    return super.invoke(input, options);
  }

  // Minimal compatibility for CascadeFlow.bindTools() tests.
  bindTools(_tools: any[], _kwargs?: any): this {
    return this;
  }

  get model() {
    return this.modelName;
  }
}

class MockStreamingChatModel extends MockChatModel {
  streamResponses: ChatGenerationChunk[][];
  streamCallCount = 0;

  constructor(modelName: string, responses: ChatResult[] = [], streamResponses: ChatGenerationChunk[][] = []) {
    super(modelName, responses);
    this.streamResponses = streamResponses;
  }

  async *_streamResponseChunks(
    _messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    _runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    this.lastOptions = options;
    const index = Math.min(this.streamCallCount, this.streamResponses.length - 1);
    const response = this.streamResponses[index];
    this.streamCallCount++;

    if (!response) {
      throw new Error('No mock stream response configured');
    }

    for (const chunk of response) {
      yield chunk;
    }
  }
}

/**
 * Helper to create a ChatResult
 */
function createChatResult(
  text: string,
  promptTokens: number,
  completionTokens: number
): ChatResult {
  return {
    generations: [
      {
        text,
        message: new AIMessage(text),
      },
    ],
    llmOutput: {
      tokenUsage: {
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      },
    },
  };
}

function createToolCallResult(toolName: string): ChatResult {
  return {
    generations: [
      {
        text: '',
        message: new AIMessage({
          content: '',
          tool_calls: [{ name: toolName, args: { x: 1 } }],
        } as any),
      },
    ],
    llmOutput: {},
  };
}

function createStreamChunks(
  parts: string[],
  promptTokens: number,
  completionTokens: number
): ChatGenerationChunk[] {
  return parts.map((part, index) => {
    const isFinal = index === parts.length - 1;
    const response_metadata = isFinal
      ? {
        tokenUsage: {
          promptTokens,
          completionTokens,
          totalTokens: promptTokens + completionTokens,
        },
      }
      : {};

    return new ChatGenerationChunk({
      text: part,
      message: new AIMessageChunk({
        content: part,
        response_metadata,
      } as any),
    });
  });
}

describe('CascadeFlow', () => {
  describe('Constructor and Configuration', () => {
    it('should initialize with default configuration', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      expect(cascade.drafter).toBe(drafter);
      expect(cascade.verifier).toBe(verifier);
      expect(cascade._llmType()).toBe('cascadeflow');
    });

    it('should accept custom quality threshold', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.9,
      });

      // Quality threshold is stored internally, we'll verify via behavior
      expect(cascade).toBeDefined();
    });

    it('should accept custom quality validator', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');
      const customValidator = vi.fn(() => 0.5);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityValidator: customValidator,
      });

      expect(cascade).toBeDefined();
    });
  });

  describe('Cascade Logic - High Quality Drafter', () => {
    it('should use drafter response when quality is above threshold', async () => {
      // Response needs >200 chars to score 0.75 (above 0.7 threshold) with new thresholds
      const drafterResponse = createChatResult(
        'The answer to 2+2 is 4. This is a basic arithmetic operation that adds two and two together. When you add the number two to another instance of the number two, the result is four. This fundamental mathematical principle is one of the first concepts taught in elementary arithmetic education.',
        14,
        8
      );
      const verifierResponse = createChatResult('2 + 2 equals 4.', 14, 10);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const messages = [new HumanMessage('What is 2+2?')];
      const result = await cascade._generate(messages, {});

      // Should use drafter response
      expect(result.generations[0].text).toBe(
        'The answer to 2+2 is 4. This is a basic arithmetic operation that adds two and two together. When you add the number two to another instance of the number two, the result is four. This fundamental mathematical principle is one of the first concepts taught in elementary arithmetic education.'
      );
      expect(drafter.callCount).toBe(1);
      expect(verifier.callCount).toBe(0); // Verifier not called

      // Check cascade stats
      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.modelUsed).toBe('drafter');
      expect(stats!.accepted).toBe(true);
      expect(stats!.drafterQuality).toBeGreaterThan(0.7);
      expect(stats!.verifierCost).toBe(0);
    });
  });

  describe('Cascade Logic - Low Quality Drafter', () => {
    it('should use verifier response when quality is below threshold', async () => {
      // Use a very short, low-quality response that will score below 0.7
      const drafterResponse = createChatResult("no", 14, 1);
      const verifierResponse = createChatResult('The answer is 4.', 14, 10);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        costTrackingProvider: 'cascadeflow',
      });

      const messages = [new HumanMessage('What is 2+2?')];
      const result = await cascade._generate(messages, {});

      // Should use verifier response
      expect(result.generations[0].text).toBe('The answer is 4.');
      expect(drafter.callCount).toBe(1);
      expect(verifier.callCount).toBe(1); // Verifier WAS called

      // Check cascade stats
      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.modelUsed).toBe('verifier');
      expect(stats!.accepted).toBe(false);
      expect(stats!.drafterQuality).toBeLessThan(0.7);
      expect(stats!.verifierCost).toBeGreaterThan(0);
    });
  });

  describe('Custom Quality Validator', () => {
    it('should use custom quality validator', async () => {
      const drafterResponse = createChatResult('Test answer', 14, 8);
      const verifierResponse = createChatResult('Better answer', 14, 10);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      // Custom validator that always returns low quality
      const customValidator = vi.fn(() => 0.3);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        qualityValidator: customValidator,
      });

      const messages = [new HumanMessage('Test')];
      await cascade._generate(messages, {});

      // Custom validator should have been called
      expect(customValidator).toHaveBeenCalled();
      expect(verifier.callCount).toBe(1); // Should cascade to verifier
    });

    it('should support async quality validator', async () => {
      const drafterResponse = createChatResult('Test answer', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [drafterResponse]);

      const asyncValidator = vi.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
        return 0.9;
      });

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        qualityValidator: asyncValidator,
      });

      const messages = [new HumanMessage('Test')];
      const result = await cascade._generate(messages, {});

      expect(asyncValidator).toHaveBeenCalled();
      expect(verifier.callCount).toBe(0); // Quality is high, no cascade
    });
  });

  describe('Cost Tracking', () => {
    it('should calculate costs correctly for accepted drafter', async () => {
      // Response needs >200 chars to score 0.75 (above 0.7 threshold) with new thresholds
      const drafterResponse = createChatResult(
        'The answer to the question is 4, which is the result of adding 2 plus 2 together. This is a fundamental arithmetic operation that demonstrates the basic principles of addition in mathematics. Understanding addition is essential for more advanced mathematical concepts and practical everyday calculations that we encounter in daily life.',
        14,
        8
      );

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', []);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        costTrackingProvider: 'cascadeflow',
      });

      const messages = [new HumanMessage('What is 2+2?')];
      await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats!.drafterCost).toBeGreaterThan(0);
      expect(stats!.verifierCost).toBe(0);
      expect(stats!.totalCost).toBe(stats!.drafterCost);
    });

    it('should calculate costs correctly for rejected drafter', async () => {
      const drafterResponse = createChatResult("no", 14, 1);
      const verifierResponse = createChatResult('The answer is 4.', 14, 10);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        costTrackingProvider: 'cascadeflow',
      });

      const messages = [new HumanMessage('What is 2+2?')];
      await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats!.drafterCost).toBeGreaterThan(0);
      expect(stats!.verifierCost).toBeGreaterThan(0);
      expect(stats!.totalCost).toBe(stats!.drafterCost + stats!.verifierCost);
    });

    it('should track latency', async () => {
      const drafterResponse = createChatResult('Answer', 14, 8);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];
      await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats!.latencyMs).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Chainable Methods - bind()', () => {
    it('should support bind() and return new CascadeFlow', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bind({ temperature: 0.5 });

      expect(boundCascade).toBeInstanceOf(CascadeFlow);
      expect(boundCascade).not.toBe(cascade); // New instance
    });

    it('should merge bind kwargs correctly', async () => {
      const drafterResponse = createChatResult('Answer', 14, 8);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bind({ temperature: 0.5 });

      const messages = [new HumanMessage('Test')];
      const result = await boundCascade._generate(messages, {});

      expect(result).toBeDefined();
      expect(drafter.callCount).toBe(1);
    });

    it('should chain multiple bind() calls', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const bound1 = cascade.bind({ temperature: 0.5 });
      const bound2 = bound1.bind({ maxTokens: 100 });

      expect(bound2).toBeInstanceOf(CascadeFlow);
    });
  });

  describe('Metadata Injection', () => {
    it('should inject cascade metadata into llmOutput', async () => {
      // Response needs >200 chars to score 0.75 (above 0.7 threshold) with new thresholds
      const drafterResponse = createChatResult(
        'The answer provided here is completely correct and demonstrates excellent understanding of the underlying concepts. This response shows a thorough grasp of the subject matter and provides clear, accurate information that addresses the question comprehensively with proper attention to detail and clarity.',
        14,
        8
      );
      const dummyResponse = createChatResult('Dummy response text here for testing purposes only.', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        enableCostTracking: true,
        costTrackingProvider: 'cascadeflow',
      });

      const messages = [new HumanMessage('Test')];
      const result = await cascade._generate(messages, {});

      // Metadata is injected even without runManager (changed in improvement)
      expect(result.llmOutput).toBeDefined();
      expect(result.llmOutput?.cascade).toBeDefined(); // Now always injected when tracking enabled

      // Verify cascade metadata structure
      expect(result.llmOutput?.cascade.modelUsed).toBe('drafter');
      expect(result.llmOutput?.cascade.drafterCost).toBeGreaterThan(0);

      // We can still get stats via getLastCascadeResult()
      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.drafterCost).toBeGreaterThan(0);
    });

    it('should not inject metadata when enableCostTracking is false', async () => {
      const drafterResponse = createChatResult('Answer', 14, 8);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        enableCostTracking: false,
      });

      const messages = [new HumanMessage('Test')];
      const result = await cascade._generate(messages, {});

      // Metadata still won't be injected without runManager
      expect(result.llmOutput?.cascade).toBeUndefined();
    });
  });

  describe('Edge Cases', () => {
    it('should accept low-risk tool calls without escalating (empty content is OK)', async () => {
      const drafterResponse = createToolCallResult('get_weather');
      const verifierResponse = createChatResult('Verifier', 10, 10);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.99, // Would reject empty text, but tool calls should be accepted by policy.
      }).bindTools([{ name: 'get_weather', description: 'Get current weather (read-only)' }]);

      const messages = [new HumanMessage('What is the weather?')];
      const result = await (cascade as any)._generate(messages, {});

      expect(result.generations[0].message).toBeDefined();
      expect(drafter.callCount).toBe(1);
      expect(verifier.callCount).toBe(0);
    });

    it('should force verifier for high-risk tool calls', async () => {
      const drafterResponse = createToolCallResult('delete_user');
      const verifierResponse = createToolCallResult('delete_user');

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.0,
      }).bindTools([{ name: 'delete_user', description: 'Permanently deletes a user account' }]);

      const messages = [new HumanMessage('Delete user 123')];
      await (cascade as any)._generate(messages, {});

      expect(drafter.callCount).toBe(1);
      expect(verifier.callCount).toBe(1);
    });

    it('should attach cascadeflow tags/metadata to nested calls (LangSmith DX)', async () => {
      const drafterResponse = createChatResult(
        'The answer provided here is completely correct and demonstrates excellent understanding of the underlying concepts. This response shows a thorough grasp of the subject matter and provides clear, accurate information that addresses the question comprehensively with proper attention to detail and clarity.',
        14,
        8
      );

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [drafterResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];
      await (cascade as any)._generate(messages, { tags: ['app'], metadata: { env: 'test' } });

      expect(drafter.lastInvokeOptions?.tags).toContain('cascadeflow');
      expect(drafter.lastInvokeOptions?.tags).toContain('cascadeflow:drafter');
      expect(drafter.lastInvokeOptions?.tags).toContain('app');
      expect(drafter.lastInvokeOptions?.metadata?.env).toBe('test');
      expect(drafter.lastInvokeOptions?.metadata?.cascadeflow?.integration).toBe('langchain');
    });

    it('should handle empty message array', async () => {
      const drafterResponse = createChatResult('Answer', 0, 5);
      const dummyResponse = createChatResult('Dummy', 0, 5);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const result = await cascade._generate([], {});
      expect(result).toBeDefined();
    });

    it('should handle quality exactly at threshold', async () => {
      const drafterResponse = createChatResult('Test answer.', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', []);

      // Custom validator that returns exactly the threshold
      const exactValidator = vi.fn(() => 0.7);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        qualityValidator: exactValidator,
      });

      const messages = [new HumanMessage('Test')];
      await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      // Quality >= threshold should be accepted
      expect(stats!.accepted).toBe(true);
      expect(verifier.callCount).toBe(0);
    });

    it('should handle missing token usage gracefully', async () => {
      const responseWithoutTokens: ChatResult = {
        generations: [
          {
            text: 'Answer',
            message: new AIMessage('Answer'),
          },
        ],
        llmOutput: {},
      };

      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [responseWithoutTokens]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];
      const result = await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats!.drafterCost).toBe(0); // No tokens = no cost
    });
  });

  describe('Domain Policies', () => {
    it('should apply domain quality threshold override', async () => {
      const drafterResponse = createChatResult('Draft answer', 14, 3);
      const verifierResponse = createChatResult('Verifier answer', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.9,
        qualityValidator: () => 0.6,
        enablePreRouter: false,
        domainPolicies: {
          finance: { qualityThreshold: 0.5 },
        },
      });

      const result = await (cascade as any)._generate(
        [new HumanMessage('Summarize earnings')],
        { metadata: { cascadeflow_domain: 'finance' } }
      );

      expect(result.generations[0].text).toBe('Draft answer');
      expect(drafter.callCount).toBe(1);
      expect(verifier.callCount).toBe(0);
      expect(result.llmOutput?.cascade?.effective_quality_threshold).toBe(0.5);
    });

    it('should force verifier for configured domain', async () => {
      const drafterResponse = createChatResult('Draft answer', 14, 3);
      const verifierResponse = createChatResult('Verifier answer', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.1,
        qualityValidator: () => 0.99,
        enablePreRouter: false,
        domainPolicies: {
          medical: { forceVerifier: true },
        },
      });

      const result = await (cascade as any)._generate(
        [new HumanMessage('Provide medical guidance')],
        { metadata: { cascadeflow: { domain: 'medical' } } }
      );

      expect(result.generations[0].text).toBe('Verifier answer');
      expect(drafter.callCount).toBe(1);
      expect(verifier.callCount).toBe(1);
      expect(result.llmOutput?.cascade?.cascade_decision).toBe('domain_policy');
    });

    it('should route directly to verifier for configured domain', async () => {
      const drafterResponse = createChatResult('Draft answer', 14, 3);
      const verifierResponse = createChatResult('Verifier answer', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
        enablePreRouter: false,
        domainPolicies: {
          legal: { directToVerifier: true },
        },
      });

      const result = await (cascade as any)._generate(
        [new HumanMessage('Review this contract')],
        { metadata: { domain: 'legal' } }
      );

      expect(result.generations[0].text).toBe('Verifier answer');
      expect(drafter.callCount).toBe(0);
      expect(verifier.callCount).toBe(1);
      expect(result.llmOutput?.cascade?.routing_reason).toBe('domain_policy_direct');
    });
  });

  describe('getLastCascadeResult', () => {
    it('should return undefined before first call', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeUndefined();
    });

    it('should return stats after successful call', async () => {
      // Response needs >200 chars to score 0.75 (above 0.7 threshold) with new thresholds
      const drafterResponse = createChatResult(
        'The answer provided is completely correct and demonstrates good understanding of the fundamental concepts involved. This explanation shows careful consideration of the topic and presents information in a clear, well-structured manner that effectively communicates the key points to the reader.',
        14,
        8
      );
      const dummyResponse = createChatResult('Dummy response for testing purposes only here.', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];
      await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.content).toBe('The answer provided is completely correct and demonstrates good understanding of the fundamental concepts involved. This explanation shows careful consideration of the topic and presents information in a clear, well-structured manner that effectively communicates the key points to the reader.');
      expect(stats!.modelUsed).toBe('drafter');
    });

    it('should update stats on each call', async () => {
      // Responses need >200 chars to score 0.75 (above 0.7 threshold) with new thresholds
      const response1 = createChatResult(
        'The first answer provided here is good and shows solid understanding of the key concepts involved in this discussion. This response demonstrates comprehensive knowledge and presents the information clearly with appropriate detail to help readers understand the main points effectively.',
        14,
        8
      );
      const response2 = createChatResult(
        'The second answer given here is even better with more detail and thorough explanation of the concepts. This response provides excellent clarity and demonstrates a deep understanding of the subject matter with well-structured reasoning that makes the content accessible to readers.',
        20,
        10
      );
      const dummyResponse = createChatResult('Dummy response for verification testing only here.', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [response1, response2]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeFlow({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];

      await cascade._generate(messages, {});
      const stats1 = cascade.getLastCascadeResult();
      expect(stats1!.content).toBe('The first answer provided here is good and shows solid understanding of the key concepts involved in this discussion. This response demonstrates comprehensive knowledge and presents the information clearly with appropriate detail to help readers understand the main points effectively.');

      await cascade._generate(messages, {});
      const stats2 = cascade.getLastCascadeResult();
      expect(stats2!.content).toBe('The second answer given here is even better with more detail and thorough explanation of the concepts. This response provides excellent clarity and demonstrates a deep understanding of the subject matter with well-structured reasoning that makes the content accessible to readers.');
    });
  });

  describe('Streaming stats', () => {
    it('should store accurate stats for accepted drafter streaming', async () => {
      const draftChunks = createStreamChunks(
        [
          'This streaming draft is high quality and well-structured, with clear reasoning, concrete details, and complete coverage of the requested answer. ',
          'It explains the rationale, includes examples, and closes with a concise summary so the response is comprehensive and confidently above the quality threshold for acceptance.',
        ],
        14,
        10
      );
      const drafter = new MockStreamingChatModel('gpt-4o-mini', [], [draftChunks]);
      const verifier = new MockStreamingChatModel('gpt-4o', [], []);
      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        costTrackingProvider: 'cascadeflow',
      });

      const streamed: string[] = [];
      for await (const chunk of (cascade as any)._streamResponseChunks([new HumanMessage('test')], {})) {
        streamed.push(chunk.text);
      }

      expect(streamed.join('')).toContain('high quality');
      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.modelUsed).toBe('drafter');
      expect(stats!.accepted).toBe(true);
      expect(stats!.drafterCost).toBeGreaterThan(0);
      expect(stats!.verifierCost).toBe(0);
      expect(stats!.savingsPercentage).toBeGreaterThan(0);
      expect(verifier.streamCallCount).toBe(0);
    });

    it('should store accurate stats for escalated streaming', async () => {
      const drafter = new MockStreamingChatModel(
        'gpt-4o-mini',
        [],
        [createStreamChunks(['no'], 14, 1)]
      );
      const verifier = new MockStreamingChatModel(
        'gpt-4o',
        [],
        [createStreamChunks(['The verified answer is 4.'], 14, 12)]
      );
      const cascade = new CascadeFlow({
        drafter,
        verifier,
        qualityThreshold: 0.7,
        costTrackingProvider: 'cascadeflow',
      });

      for await (const chunk of (cascade as any)._streamResponseChunks([new HumanMessage('What is 2+2?')], {})) {
        void chunk;
        // consume stream
      }

      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.modelUsed).toBe('verifier');
      expect(stats!.accepted).toBe(false);
      expect(stats!.drafterCost).toBeGreaterThan(0);
      expect(stats!.verifierCost).toBeGreaterThan(0);
      expect(stats!.totalCost).toBe(stats!.drafterCost + stats!.verifierCost);
    });

    it('should store stats for direct-to-verifier streaming by domain policy', async () => {
      const drafter = new MockStreamingChatModel('gpt-4o-mini', [], []);
      const verifier = new MockStreamingChatModel(
        'gpt-4o',
        [],
        [createStreamChunks(['Direct verifier path answer.'], 20, 9)]
      );
      const cascade = new CascadeFlow({
        drafter,
        verifier,
        enablePreRouter: false,
        costTrackingProvider: 'cascadeflow',
        domainPolicies: {
          legal: { directToVerifier: true },
        },
      });

      for await (const chunk of (cascade as any)._streamResponseChunks(
        [new HumanMessage('Review this contract')],
        { metadata: { domain: 'legal' } }
      )) {
        void chunk;
        // consume stream
      }

      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.modelUsed).toBe('verifier');
      expect(stats!.accepted).toBe(false);
      expect(stats!.drafterCost).toBe(0);
      expect(stats!.verifierCost).toBeGreaterThan(0);
      expect(drafter.streamCallCount).toBe(0);
      expect(verifier.streamCallCount).toBe(1);
    });
  });
});
