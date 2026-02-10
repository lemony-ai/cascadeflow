/**
 * LCEL Pipeline Example (CascadeFlow + LangChain Expression Language)
 *
 * Demonstrates:
 * - Prompt -> CascadeFlow -> parser composition via `.pipe(...)`
 * - LangSmith tags/metadata propagation through CascadeFlow nested runs
 *
 * Setup:
 *   export OPENAI_API_KEY="sk-..."
 *   pnpm -C packages/langchain-cascadeflow install
 *   npx tsx packages/langchain-cascadeflow/examples/lcel-pipeline.ts
 */

import { ChatOpenAI } from '@langchain/openai';
import { ChatPromptTemplate } from '@langchain/core/prompts';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { withCascade } from '../src/index.js';

async function main() {
  if (!process.env.OPENAI_API_KEY) {
    console.log("Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'");
    process.exit(1);
  }

  const drafter = new ChatOpenAI({ model: 'gpt-4o-mini', temperature: 0.2 });
  const verifier = new ChatOpenAI({ model: 'gpt-4o', temperature: 0.2 });

  const cascade = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    costTrackingProvider: 'langsmith',
  });

  const prompt = ChatPromptTemplate.fromMessages([
    ['system', 'You are a concise engineer.'],
    ['human', '{question}'],
  ]);

  const chain = prompt.pipe(cascade).pipe(new StringOutputParser());

  const out = await chain.invoke(
    { question: 'List 3 pitfalls when designing agent tool loops.' },
    {
      tags: ['example', 'lcel'],
      metadata: { example: 'lcel-pipeline' },
    }
  );

  console.log(out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

