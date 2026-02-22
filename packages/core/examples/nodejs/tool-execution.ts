/**
 * Tool Execution Example
 *
 * Demonstrates tool calling capabilities with cascadeflow:
 * - Defining custom tools
 * - Tool execution with cascade
 * - Multi-step tool workflows
 * - Error handling in tool calls
 * - Tool result validation
 *
 * Usage: npx tsx examples/nodejs/tool-execution.ts
 */

import { CascadeAgent } from '@cascadeflow/core';
import { safeCalculateExpression } from './safe-math';

// ============================================================================
// Tool Definitions
// ============================================================================

/**
 * Weather tool - simulates weather API
 */
const weatherTool = {
  type: 'function' as const,
  function: {
    name: 'get_weather',
    description: 'Get current weather for a location',
    parameters: {
      type: 'object',
      properties: {
        location: {
          type: 'string',
          description: 'City name or coordinates'
        },
        units: {
          type: 'string',
          enum: ['celsius', 'fahrenheit'],
          description: 'Temperature units'
        }
      },
      required: ['location']
    }
  }
};

/**
 * Calculator tool - performs mathematical operations
 */
const calculatorTool = {
  type: 'function' as const,
  function: {
    name: 'calculate',
    description: 'Perform mathematical calculations',
    parameters: {
      type: 'object',
      properties: {
        expression: {
          type: 'string',
          description: 'Mathematical expression to evaluate (e.g., "2 + 2", "sqrt(16)")'
        }
      },
      required: ['expression']
    }
  }
};

/**
 * Search tool - simulates database search
 */
const searchTool = {
  type: 'function' as const,
  function: {
    name: 'search_database',
    description: 'Search a product database',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query'
        },
        category: {
          type: 'string',
          enum: ['electronics', 'books', 'clothing', 'all'],
          description: 'Product category filter'
        },
        max_results: {
          type: 'number',
          description: 'Maximum number of results to return'
        }
      },
      required: ['query']
    }
  }
};

/**
 * Email tool - simulates sending emails
 */
const emailTool = {
  type: 'function' as const,
  function: {
    name: 'send_email',
    description: 'Send an email to a recipient',
    parameters: {
      type: 'object',
      properties: {
        to: {
          type: 'string',
          description: 'Recipient email address'
        },
        subject: {
          type: 'string',
          description: 'Email subject line'
        },
        body: {
          type: 'string',
          description: 'Email body content'
        }
      },
      required: ['to', 'subject', 'body']
    }
  }
};

// ============================================================================
// Tool Execution Functions
// ============================================================================

/**
 * Execute weather tool
 */
function executeWeatherTool(args: { location: string; units?: string }): string {
  const { location, units = 'celsius' } = args;

  // Simulate weather data
  const temp = units === 'celsius' ? 22 : 72;
  const conditions = ['sunny', 'cloudy', 'rainy', 'partly cloudy'];
  const condition = conditions[Math.floor(Math.random() * conditions.length)];

  return JSON.stringify({
    location,
    temperature: temp,
    units,
    condition,
    humidity: 65,
    wind_speed: 12
  });
}

/**
 * Execute calculator tool
 */
function executeCalculatorTool(args: { expression: string }): string {
  try {
    const result = safeCalculateExpression(args.expression);
    return JSON.stringify({
      expression: args.expression,
      result,
      unit: typeof result === 'number' ? 'number' : 'unknown'
    });
  } catch (error) {
    return JSON.stringify({
      error: 'Calculation failed',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}

/**
 * Execute search tool
 */
function executeSearchTool(args: { query: string; category?: string; max_results?: number }): string {
  const { query, category = 'all', max_results = 5 } = args;

  // Simulate search results
  const products = [
    { id: 1, name: 'Laptop Pro', category: 'electronics', price: 1299 },
    { id: 2, name: 'TypeScript Book', category: 'books', price: 39 },
    { id: 3, name: 'Wireless Mouse', category: 'electronics', price: 29 },
    { id: 4, name: 'Cotton T-Shirt', category: 'clothing', price: 19 },
    { id: 5, name: 'Programming Guide', category: 'books', price: 49 },
  ];

  let results = products;
  if (category !== 'all') {
    results = results.filter(p => p.category === category);
  }

  // Simple search filter
  results = results.filter(p =>
    p.name.toLowerCase().includes(query.toLowerCase())
  );

  return JSON.stringify({
    query,
    category,
    total_results: results.length,
    results: results.slice(0, max_results)
  });
}

/**
 * Execute email tool
 */
function executeEmailTool(args: { to: string; subject: string; body: string }): string {
  // Simulate email sending
  return JSON.stringify({
    status: 'sent',
    to: args.to,
    subject: args.subject,
    timestamp: new Date().toISOString(),
    message_id: `msg_${Math.random().toString(36).substr(2, 9)}`
  });
}

/**
 * Tool execution dispatcher
 */
function executeToolCall(toolName: string, args: any): string {
  switch (toolName) {
    case 'get_weather':
      return executeWeatherTool(args);
    case 'calculate':
      return executeCalculatorTool(args);
    case 'search_database':
      return executeSearchTool(args);
    case 'send_email':
      return executeEmailTool(args);
    default:
      return JSON.stringify({ error: 'Unknown tool', tool: toolName });
  }
}

// ============================================================================
// Example Scenarios
// ============================================================================

async function main() {
  console.log('\n╔═══════════════════════════════════════════════════════════════╗');
  console.log('║         cascadeflow - Tool Execution Examples                ║');
  console.log('╚═══════════════════════════════════════════════════════════════╝\n');

  // Check for API key
  if (!process.env.OPENAI_API_KEY) {
    console.log('⚠️  OPENAI_API_KEY not found in environment');
    console.log('   Set it in .env file or export OPENAI_API_KEY=your_key');
    console.log('   This example requires OpenAI for tool calling support\n');
    return;
  }

  // Initialize agent with tool support
  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
        supportsTools: true,
      },
      {
        name: 'gpt-4o',
        provider: 'openai',
        cost: 0.00625,
        supportsTools: true,
      },
    ],
    quality: {
      threshold: 0.7,
    },
  });

  console.log('🔧 Tool calling capabilities:');
  console.log('   • Weather lookups');
  console.log('   • Mathematical calculations');
  console.log('   • Database searches');
  console.log('   • Email sending (simulated)');
  console.log('');

  // ======================================================================
  // Example 1: Single Tool Call (Weather)
  // ======================================================================
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 1: Single Tool Call (Weather)');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const result1 = await agent.run(
      "What's the weather like in San Francisco?",
      {
        maxTokens: 150,
        tools: [weatherTool],
      }
    );

    console.log('Query: What\'s the weather like in San Francisco?');
    console.log(`Model: ${result1.modelUsed}`);

    if (result1.toolCalls && result1.toolCalls.length > 0) {
      console.log(`\n🔧 Tool Calls Made: ${result1.toolCalls.length}`);

      for (const toolCall of result1.toolCalls) {
        console.log(`\n   Tool: ${toolCall.function.name}`);
        console.log(`   Arguments: ${toolCall.function.arguments}`);

        // Execute the tool
        const toolResult = executeToolCall(
          toolCall.function.name,
          JSON.parse(toolCall.function.arguments)
        );
        console.log(`   Result: ${toolResult}`);
      }
    }

    console.log(`\n💬 Response: ${result1.content}`);
    console.log(`💰 Cost: $${result1.totalCost.toFixed(6)}`);
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 2: Multiple Tool Calls (Calculator)
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 2: Mathematical Calculations');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const result2 = await agent.run(
      "Calculate the square root of 144 and then multiply it by 5",
      {
        maxTokens: 200,
        tools: [calculatorTool],
      }
    );

    console.log('Query: Calculate sqrt(144) * 5');
    console.log(`Model: ${result2.modelUsed}`);

    if (result2.toolCalls && result2.toolCalls.length > 0) {
      console.log(`\n🔧 Tool Calls Made: ${result2.toolCalls.length}`);

      for (let i = 0; i < result2.toolCalls.length; i++) {
        const toolCall = result2.toolCalls[i];
        console.log(`\n   Call ${i + 1}:`);
        console.log(`   Tool: ${toolCall.function.name}`);
        console.log(`   Expression: ${JSON.parse(toolCall.function.arguments).expression}`);

        const toolResult = executeToolCall(
          toolCall.function.name,
          JSON.parse(toolCall.function.arguments)
        );
        const parsed = JSON.parse(toolResult);
        console.log(`   Result: ${parsed.result}`);
      }
    }

    console.log(`\n💬 Response: ${result2.content}`);
    console.log(`💰 Cost: $${result2.totalCost.toFixed(6)}`);
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 3: Database Search
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 3: Database Search');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const result3 = await agent.run(
      "Search for electronics products",
      {
        maxTokens: 200,
        tools: [searchTool],
      }
    );

    console.log('Query: Search for electronics products');
    console.log(`Model: ${result3.modelUsed}`);

    if (result3.toolCalls && result3.toolCalls.length > 0) {
      for (const toolCall of result3.toolCalls) {
        console.log(`\n🔧 Tool: ${toolCall.function.name}`);

        const toolResult = executeToolCall(
          toolCall.function.name,
          JSON.parse(toolCall.function.arguments)
        );
        const parsed = JSON.parse(toolResult);

        console.log(`   Query: "${parsed.query}"`);
        console.log(`   Category: ${parsed.category}`);
        console.log(`   Results: ${parsed.total_results} found`);

        if (parsed.results && parsed.results.length > 0) {
          console.log('\n   Products:');
          parsed.results.forEach((product: any, idx: number) => {
            console.log(`   ${idx + 1}. ${product.name} - $${product.price}`);
          });
        }
      }
    }

    console.log(`\n💬 Response: ${result3.content}`);
    console.log(`💰 Cost: $${result3.totalCost.toFixed(6)}`);
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 4: Multi-Tool Workflow
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 4: Multi-Tool Workflow');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const result4 = await agent.run(
      "Check the weather in New York and send me an email about it",
      {
        maxTokens: 250,
        tools: [weatherTool, emailTool],
      }
    );

    console.log('Query: Check weather and send email');
    console.log(`Model: ${result4.modelUsed}`);

    if (result4.toolCalls && result4.toolCalls.length > 0) {
      console.log(`\n🔧 Multi-Step Workflow: ${result4.toolCalls.length} tools used\n`);

      for (let i = 0; i < result4.toolCalls.length; i++) {
        const toolCall = result4.toolCalls[i];
        console.log(`   Step ${i + 1}: ${toolCall.function.name}`);

        const toolResult = executeToolCall(
          toolCall.function.name,
          JSON.parse(toolCall.function.arguments)
        );
        const parsed = JSON.parse(toolResult);

        if (toolCall.function.name === 'get_weather') {
          console.log(`   └─ Location: ${parsed.location}`);
          console.log(`   └─ Temperature: ${parsed.temperature}°${parsed.units === 'celsius' ? 'C' : 'F'}`);
          console.log(`   └─ Condition: ${parsed.condition}`);
        } else if (toolCall.function.name === 'send_email') {
          console.log(`   └─ To: ${parsed.to}`);
          console.log(`   └─ Subject: ${parsed.subject}`);
          console.log(`   └─ Status: ${parsed.status}`);
        }
        console.log('');
      }
    }

    console.log(`💬 Response: ${result4.content}`);
    console.log(`💰 Cost: $${result4.totalCost.toFixed(6)}`);
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 5: Tool Error Handling
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 5: Error Handling');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const result5 = await agent.run(
      "Calculate the result of dividing by zero: 10 / 0",
      {
        maxTokens: 150,
        tools: [calculatorTool],
      }
    );

    console.log('Query: Calculate 10 / 0 (error case)');
    console.log(`Model: ${result5.modelUsed}`);

    if (result5.toolCalls && result5.toolCalls.length > 0) {
      for (const toolCall of result5.toolCalls) {
        const toolResult = executeToolCall(
          toolCall.function.name,
          JSON.parse(toolCall.function.arguments)
        );
        const parsed = JSON.parse(toolResult);

        console.log('\n🔧 Tool Call Result:');
        if (parsed.error) {
          console.log(`   ⚠️  Error: ${parsed.error}`);
          console.log(`   Message: ${parsed.message}`);
        } else {
          console.log(`   Result: ${parsed.result}`);
        }
      }
    }

    console.log(`\n💬 Response: ${result5.content}`);
    console.log(`💰 Cost: $${result5.totalCost.toFixed(6)}`);
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Summary
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📊 Tool Calling Summary');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  console.log('✅ Demonstrated Features:');
  console.log('   • Single tool calls');
  console.log('   • Multiple sequential tool calls');
  console.log('   • Multi-tool workflows');
  console.log('   • Error handling');
  console.log('   • Tool result parsing');
  console.log('');
  console.log('🎯 Key Takeaways:');
  console.log('   • Tools are passed via the tools parameter');
  console.log('   • cascadeflow works with any tool-compatible provider');
  console.log('   • Tool results are returned in result.toolCalls');
  console.log('   • You execute tools and feed results back as needed');
  console.log('   • Cost optimization applies to tool-using queries too');
  console.log('');
  console.log('📚 Learn More:');
  console.log('   • See streaming-tools.ts for streaming with tools');
  console.log('   • See multi-step-cascade.ts for complex workflows');
  console.log('');
}

// Run examples
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
