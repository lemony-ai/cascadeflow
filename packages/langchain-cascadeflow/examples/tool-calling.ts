/**
 * Tool Calling Example
 *
 * Demonstrates how to use LangChain tools with CascadeFlow.
 * Tools are preserved when using cascade, allowing the drafter or verifier
 * to make function calls as needed.
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

async function main() {
  console.log('=== CascadeFlow Tool Calling Demo ===\n');

  const drafter = new ChatOpenAI({ model: 'gpt-4o-mini', temperature: 0 });
  const verifier = new ChatOpenAI({ model: 'gpt-4o', temperature: 0 });

  // Define tools
  const tools = [
    {
      name: 'calculator',
      description: 'Performs basic arithmetic operations. Use this when you need to calculate numbers.',
      parameters: {
        type: 'object',
        properties: {
          operation: {
            type: 'string',
            enum: ['add', 'subtract', 'multiply', 'divide'],
            description: 'The arithmetic operation to perform',
          },
          a: {
            type: 'number',
            description: 'First number',
          },
          b: {
            type: 'number',
            description: 'Second number',
          },
        },
        required: ['operation', 'a', 'b'],
      },
    },
    {
      name: 'get_current_weather',
      description: 'Get the current weather for a location',
      parameters: {
        type: 'object',
        properties: {
          location: {
            type: 'string',
            description: 'The city and state, e.g. San Francisco, CA',
          },
          unit: {
            type: 'string',
            enum: ['celsius', 'fahrenheit'],
            description: 'Temperature unit',
          },
        },
        required: ['location'],
      },
    },
  ];

  // Example 1: Simple tool calling (uses drafter)
  console.log('--- Example 1: Simple Calculator (Drafter) ---');

  const cascade1 = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
  });

  const boundCascade1 = cascade1.bindTools(tools);
  const result1 = await boundCascade1.invoke('What is 15 plus 27?');

  console.log('Query: What is 15 plus 27?');
  console.log(`Response: ${result1.content}`);

  const metadata1 = cascade1.getLastCascadeResult();
  console.log(`Model used: ${metadata1?.modelUsed}`);
  console.log(`Quality: ${metadata1?.drafterQuality?.toFixed(2)}`);
  console.log('\n');

  // Example 2: Complex multi-tool query (may use verifier)
  console.log('--- Example 2: Multi-Tool Query ---');

  const cascade2 = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
  });

  const boundCascade2 = cascade2.bindTools(tools);
  const result2 = await boundCascade2.invoke(
    'What is the weather in San Francisco? Also, calculate 100 divided by 4.'
  );

  console.log('Query: What is the weather in San Francisco? Also, calculate 100 divided by 4.');
  console.log(`Response: ${result2.content}`);

  const metadata2 = cascade2.getLastCascadeResult();
  console.log(`Model used: ${metadata2?.modelUsed}`);
  console.log(`Quality: ${metadata2?.drafterQuality?.toFixed(2)}`);
  console.log('\n');

  // Example 3: Structured Output
  console.log('--- Example 3: Structured Output ---');

  const userSchema = {
    type: 'object',
    properties: {
      name: { type: 'string', description: 'The person\'s name' },
      age: { type: 'number', description: 'The person\'s age' },
      email: { type: 'string', description: 'Email address' },
      interests: {
        type: 'array',
        items: { type: 'string' },
        description: 'List of interests',
      },
    },
    required: ['name', 'age'],
  };

  const cascade3 = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
  });

  const structuredCascade = cascade3.withStructuredOutput(userSchema);
  const result3 = await structuredCascade.invoke(
    'Extract user info: John Smith is 28 years old, email john@example.com, interested in programming and music.'
  );

  console.log('Query: Extract user info from text');
  console.log('Structured result:', JSON.stringify(result3, null, 2));

  const metadata3 = cascade3.getLastCascadeResult();
  console.log(`Model used: ${metadata3?.modelUsed}`);
  console.log('\n');

  // Example 4: Chaining bind() with bindTools()
  console.log('--- Example 4: Method Chaining ---');

  const cascade4 = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
  });

  const chainedCascade = cascade4
    .bind({ temperature: 0.3 }) // Lower temperature for more deterministic results
    .bindTools([tools[0]]); // Only bind calculator tool

  const result4 = await chainedCascade.invoke('Calculate 456 multiplied by 789');

  console.log('Query: Calculate 456 multiplied by 789');
  console.log(`Response: ${result4.content}`);

  const metadata4 = cascade4.getLastCascadeResult();
  console.log(`Model used: ${metadata4?.modelUsed}`);
  console.log('\n');

  // Example 5: Quality-based routing with tools
  console.log('--- Example 5: Force Verifier with High Threshold ---');

  const cascade5 = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.99, // Very high threshold, forces verifier
  });

  const boundCascade5 = cascade5.bindTools(tools);
  const result5 = await boundCascade5.invoke('What is 7 + 8?');

  console.log('Query: What is 7 + 8? (high quality threshold)');
  console.log(`Response: ${result5.content}`);

  const metadata5 = cascade5.getLastCascadeResult();
  console.log(`Model used: ${metadata5?.modelUsed} (forced by high threshold)`);
  console.log(`Drafter quality: ${metadata5?.drafterQuality?.toFixed(2)}`);
  console.log(`Threshold: 0.99`);
  console.log('\n');

  console.log('=== Tool Calling Demo Complete ===');
  console.log('\n💡 Tools are preserved and work seamlessly with cascade');
  console.log('💡 The cascade automatically chooses drafter or verifier');
  console.log('💡 Both .bindTools() and .withStructuredOutput() are supported');
  console.log('💡 Method chaining works as expected');
}

main().catch(console.error);
