import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, HumanMessage, AIMessage } from '@langchain/core/messages';
import { ChatResult, ChatGeneration } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { CascadeWrapper } from './wrapper.js';

/**
 * Mock chat model for testing
 */
class MockChatModel extends BaseChatModel {
  modelName: string;
  responses: ChatResult[];
  callCount = 0;

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
    const index = Math.min(this.callCount, this.responses.length - 1);
    const response = this.responses[index];
    this.callCount++;
    if (!response) {
      throw new Error('No mock response configured');
    }
    return response;
  }

  get model() {
    return this.modelName;
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

describe('CascadeWrapper', () => {
  describe('Constructor and Configuration', () => {
    it('should initialize with default configuration', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      expect(cascade.drafter).toBe(drafter);
      expect(cascade.verifier).toBe(verifier);
      expect(cascade._llmType()).toBe('cascade-wrapper');
    });

    it('should accept custom quality threshold', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeWrapper({
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

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityValidator: customValidator,
      });

      expect(cascade).toBeDefined();
    });
  });

  describe('Cascade Logic - High Quality Drafter', () => {
    it('should use drafter response when quality is above threshold', async () => {
      const drafterResponse = createChatResult('The answer is 4.', 14, 8);
      const verifierResponse = createChatResult('2 + 2 equals 4.', 14, 10);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [verifierResponse]);

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const messages = [new HumanMessage('What is 2+2?')];
      const result = await cascade._generate(messages, {});

      // Should use drafter response
      expect(result.generations[0].text).toBe('The answer is 4.');
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

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
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

      const cascade = new CascadeWrapper({
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

      const cascade = new CascadeWrapper({
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
      const drafterResponse = createChatResult('The answer is 4.', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', []);

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
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

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
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

      const cascade = new CascadeWrapper({
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
    it('should support bind() and return new CascadeWrapper', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bind({ temperature: 0.5 });

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
      expect(boundCascade).not.toBe(cascade); // New instance
    });

    it('should merge bind kwargs correctly', async () => {
      const drafterResponse = createChatResult('Answer', 14, 8);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeWrapper({
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

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const bound1 = cascade.bind({ temperature: 0.5 });
      const bound2 = bound1.bind({ maxTokens: 100 });

      expect(bound2).toBeInstanceOf(CascadeWrapper);
    });
  });

  describe('Metadata Injection', () => {
    it('should inject cascade metadata into llmOutput', async () => {
      const drafterResponse = createChatResult('The answer is correct.', 14, 8);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        enableCostTracking: true,
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

      const cascade = new CascadeWrapper({
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
    it('should handle empty message array', async () => {
      const drafterResponse = createChatResult('Answer', 0, 5);
      const dummyResponse = createChatResult('Dummy', 0, 5);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeWrapper({
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

      const cascade = new CascadeWrapper({
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

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];
      const result = await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats!.drafterCost).toBe(0); // No tokens = no cost
    });
  });

  describe('getLastCascadeResult', () => {
    it('should return undefined before first call', () => {
      const drafter = new MockChatModel('gpt-4o-mini');
      const verifier = new MockChatModel('gpt-4o');

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeUndefined();
    });

    it('should return stats after successful call', async () => {
      const drafterResponse = createChatResult('The answer is correct.', 14, 8);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [drafterResponse]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];
      await cascade._generate(messages, {});

      const stats = cascade.getLastCascadeResult();
      expect(stats).toBeDefined();
      expect(stats!.content).toBe('The answer is correct.');
      expect(stats!.modelUsed).toBe('drafter');
    });

    it('should update stats on each call', async () => {
      const response1 = createChatResult('The first answer is good.', 14, 8);
      const response2 = createChatResult('The second answer is better.', 20, 10);
      const dummyResponse = createChatResult('Dummy', 14, 8);

      const drafter = new MockChatModel('gpt-4o-mini', [response1, response2]);
      const verifier = new MockChatModel('gpt-4o', [dummyResponse]);

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const messages = [new HumanMessage('Test')];

      await cascade._generate(messages, {});
      const stats1 = cascade.getLastCascadeResult();
      expect(stats1!.content).toBe('The first answer is good.');

      await cascade._generate(messages, {});
      const stats2 = cascade.getLastCascadeResult();
      expect(stats2!.content).toBe('The second answer is better.');
    });
  });
});
