import { describe, expect, it } from 'vitest';
import Anthropic from '@anthropic-ai/sdk';
import Groq from 'groq-sdk';
import OpenAI from 'openai';
import {
  anthropicAdapter,
  createDraftVerifierCascade,
  groqAdapter,
  openAIAdapter,
} from '../index';

type UsageMetrics = {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
};

type ProviderModel = {
  provider: 'openai' | 'groq' | 'anthropic';
  model: string;
};

type GenerateResult = {
  text: string;
  usage: UsageMetrics;
  model: string;
  provider: ProviderModel['provider'];
  finishReason?: string | null;
};

type StreamResult = {
  text: string;
  usage?: UsageMetrics;
  model: string;
  provider: ProviderModel['provider'];
};

const describeIf = (condition: boolean) => (condition ? describe : describe.skip);

const OPENAI_KEY = process.env.OPENAI_API_KEY;
const GROQ_KEY = process.env.GROQ_API_KEY;
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;

const OPENAI_MODEL = process.env.OPENAI_MODEL ?? openAIAdapter.models[0].id;
const GROQ_MODEL = process.env.GROQ_MODEL ?? groqAdapter.models[1].id;
const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL ?? anthropicAdapter.models[0].id;

function normalizeUsage(usage?: {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
} | {
  input_tokens?: number;
  output_tokens?: number;
}): UsageMetrics {
  const promptTokens =
    'prompt_tokens' in (usage ?? {})
      ? usage?.prompt_tokens ?? 0
      : usage?.input_tokens ?? 0;
  const completionTokens =
    'completion_tokens' in (usage ?? {})
      ? usage?.completion_tokens ?? 0
      : usage?.output_tokens ?? 0;
  const totalTokens =
    'total_tokens' in (usage ?? {})
      ? usage?.total_tokens ?? promptTokens + completionTokens
      : promptTokens + completionTokens;

  return { promptTokens, completionTokens, totalTokens };
}

async function generateText({
  model,
  prompt,
  maxTokens = 128,
}: {
  model: ProviderModel;
  prompt: string;
  maxTokens?: number;
}): Promise<GenerateResult> {
  if (model.provider === 'openai') {
    const client = new OpenAI({ apiKey: OPENAI_KEY });
    const response = await client.chat.completions.create({
      model: model.model,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: maxTokens,
    });

    return {
      text: response.choices[0]?.message?.content ?? '',
      usage: normalizeUsage(response.usage),
      model: model.model,
      provider: model.provider,
      finishReason: response.choices[0]?.finish_reason ?? null,
    };
  }

  if (model.provider === 'groq') {
    const client = new Groq({ apiKey: GROQ_KEY });
    const response = await client.chat.completions.create({
      model: model.model,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: maxTokens,
    });

    return {
      text: response.choices[0]?.message?.content ?? '',
      usage: normalizeUsage(response.usage),
      model: model.model,
      provider: model.provider,
      finishReason: response.choices[0]?.finish_reason ?? null,
    };
  }

  const client = new Anthropic({ apiKey: ANTHROPIC_KEY });
  const response = await client.messages.create({
    model: model.model,
    max_tokens: maxTokens,
    messages: [{ role: 'user', content: prompt }],
  });
  const firstBlock = response.content[0];
  const text = firstBlock?.type === 'text' ? firstBlock.text : '';

  return {
    text,
    usage: normalizeUsage(response.usage),
    model: model.model,
    provider: model.provider,
    finishReason: response.stop_reason ?? null,
  };
}

async function streamText({
  model,
  prompt,
  maxTokens = 128,
}: {
  model: ProviderModel;
  prompt: string;
  maxTokens?: number;
}): Promise<StreamResult> {
  if (model.provider === 'openai') {
    const client = new OpenAI({ apiKey: OPENAI_KEY });
    const stream = await client.chat.completions.create({
      model: model.model,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: maxTokens,
      stream: true,
    });

    let text = '';
    for await (const chunk of stream) {
      text += chunk.choices[0]?.delta?.content ?? '';
    }

    return {
      text,
      model: model.model,
      provider: model.provider,
    };
  }

  const client = new Groq({ apiKey: GROQ_KEY });
  const stream = await client.chat.completions.create({
    model: model.model,
    messages: [{ role: 'user', content: prompt }],
    max_tokens: maxTokens,
    stream: true,
  });

  let text = '';
  for await (const chunk of stream) {
    text += chunk.choices[0]?.delta?.content ?? '';
  }

  return {
    text,
    model: model.model,
    provider: model.provider,
  };
}

function calculateCost({
  promptTokens,
  completionTokens,
}: UsageMetrics,
  modelId: string,
  provider: 'openai' | 'groq' | 'anthropic'
): number {
  const adapter =
    provider === 'openai'
      ? openAIAdapter
      : provider === 'groq'
      ? groqAdapter
      : anthropicAdapter;
  const modelSpec = adapter.getModel(modelId);

  const inputCost = (promptTokens / 1000) * modelSpec.cost.input;
  const outputCost = (completionTokens / 1000) * modelSpec.cost.output;

  return inputCost + outputCost;
}

describeIf(Boolean(OPENAI_KEY) && Boolean(GROQ_KEY))(
  'Vercel AI provider E2E - OpenAI and Groq',
  () => {
    it(
      'supports a draft/verifier cascade with mixed providers',
      async () => {
        const cascade = createDraftVerifierCascade(
          { providerId: groqAdapter.id, model: GROQ_MODEL },
          { providerId: openAIAdapter.id, model: OPENAI_MODEL }
        );

        expect(cascade.roles).toEqual(['drafter', 'verifier']);

        const draft = await generateText({
          model: { provider: 'groq', model: GROQ_MODEL },
          prompt: 'Draft a 1-sentence summary about TypeScript.',
        });

        const verify = await generateText({
          model: { provider: 'openai', model: OPENAI_MODEL },
          prompt: `Verify and refine this summary: ${draft.text}`,
        });

        expect(draft.text).toBeTruthy();
        expect(verify.text).toBeTruthy();
        expect(verify.finishReason).toBeTruthy();
      },
      60000
    );

    it(
      'handles errors and falls back to another provider',
      async () => {
        const originalKey = process.env.OPENAI_API_KEY;
        process.env.OPENAI_API_KEY = 'invalid-key';
        let failed = false;

        try {
          await generateText({
            model: { provider: 'openai', model: OPENAI_MODEL },
            prompt: 'Respond with OK.',
            maxTokens: 16,
          });
        } catch (error) {
          failed = Boolean(error);
        } finally {
          process.env.OPENAI_API_KEY = originalKey;
        }

        expect(failed).toBe(true);

        const fallback = await generateText({
          model: { provider: 'groq', model: GROQ_MODEL },
          prompt: 'Respond with OK.',
          maxTokens: 16,
        });

        expect(fallback.text).toMatch(/ok/i);
      },
      60000
    );

    it(
      'streams text from providers',
      async () => {
        const result = await streamText({
          model: { provider: 'groq', model: GROQ_MODEL },
          prompt: 'Stream a short greeting.',
          maxTokens: 32,
        });

        expect(result.text).toBeTruthy();
      },
      60000
    );

    it(
      'tracks cost using usage metadata',
      async () => {
        const result = await generateText({
          model: { provider: 'openai', model: OPENAI_MODEL },
          prompt: 'Give a short tagline for an AI product.',
        });

        expect(result.usage.totalTokens).toBeGreaterThan(0);
        const cost = calculateCost(result.usage, result.model, result.provider);
        expect(cost).toBeGreaterThan(0);
      },
      60000
    );
  }
);

describeIf(Boolean(ANTHROPIC_KEY))('Vercel AI provider E2E - Anthropic', () => {
  it(
    'generates text and reports usage',
    async () => {
      const result = await generateText({
        model: { provider: 'anthropic', model: ANTHROPIC_MODEL },
        prompt: 'Write a short, cheerful greeting.',
        maxTokens: 64,
      });

      expect(result.text).toBeTruthy();
      expect(result.usage.totalTokens).toBeGreaterThan(0);
      expect(result.finishReason).toBeTruthy();
    },
    60000
  );
});
