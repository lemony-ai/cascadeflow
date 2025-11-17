/**
 * Metadata Inspection Script
 *
 * Checks what metadata is actually being injected into responses
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

async function main() {
  const drafter = new ChatOpenAI({ model: 'gpt-4o-mini', temperature: 0.7 });
  const verifier = new ChatOpenAI({ model: 'gpt-4o', temperature: 0.7 });

  const cascadeModel = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enableCostTracking: true,
  });

  console.log('Testing metadata injection...\n');

  // Test with simple query
  const result = await cascadeModel.invoke('What is 2+2?');

  console.log('=== Response Structure ===');
  console.log('Content:', result.content);
  console.log('\n=== Additional Kwargs ===');
  console.log(JSON.stringify(result.additional_kwargs, null, 2));

  console.log('\n=== Response Metadata ===');
  console.log(JSON.stringify(result.response_metadata, null, 2));

  console.log('\n=== Last Cascade Result ===');
  const stats = cascadeModel.getLastCascadeResult();
  console.log(JSON.stringify(stats, null, 2));

  // Test calling _generate directly to see llmOutput
  console.log('\n\n=== Testing _generate directly ===');
  const { HumanMessage } = await import('@langchain/core/messages');
  const chatResult = await cascadeModel._generate([new HumanMessage('What is the capital of France?')], {});

  console.log('llmOutput:', JSON.stringify(chatResult.llmOutput, null, 2));
  console.log('\nGeneration text:', chatResult.generations[0].text);
}

main().catch(console.error);
