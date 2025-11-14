/**
 * Streaming with Tools Example
 *
 * Demonstrates combining streaming and tool calling:
 * - Real-time streaming with tool execution
 * - Tool call events in stream
 * - Progressive response building
 * - Multi-step tool workflows with streaming
 *
 * Usage: npx tsx examples/nodejs/streaming-tools.ts
 */

import { CascadeAgent, StreamEventType } from '@cascadeflow/core';

// ============================================================================
// Tool Definitions
// ============================================================================

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

const stockTool = {
  type: 'function' as const,
  function: {
    name: 'get_stock_price',
    description: 'Get current stock price',
    parameters: {
      type: 'object',
      properties: {
        symbol: {
          type: 'string',
          description: 'Stock ticker symbol (e.g., AAPL, GOOGL)'
        }
      },
      required: ['symbol']
    }
  }
};

const searchTool = {
  type: 'function' as const,
  function: {
    name: 'search_web',
    description: 'Search the web for information',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query'
        },
        num_results: {
          type: 'number',
          description: 'Number of results to return (1-10)'
        }
      },
      required: ['query']
    }
  }
};

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
          description: 'Mathematical expression to evaluate'
        }
      },
      required: ['expression']
    }
  }
};

// ============================================================================
// Tool Execution Functions
// ============================================================================

function executeWeatherTool(args: { location: string; units?: string }): any {
  const { location, units = 'celsius' } = args;
  const temp = units === 'celsius' ? Math.floor(Math.random() * 30) + 10 : Math.floor(Math.random() * 54) + 50;
  const conditions = ['sunny', 'cloudy', 'rainy', 'partly cloudy', 'clear'];

  return {
    location,
    temperature: temp,
    units,
    condition: conditions[Math.floor(Math.random() * conditions.length)],
    humidity: Math.floor(Math.random() * 40) + 50,
    wind_speed: Math.floor(Math.random() * 20) + 5
  };
}

function executeStockTool(args: { symbol: string }): any {
  const basePrice = Math.random() * 500 + 50;
  return {
    symbol: args.symbol.toUpperCase(),
    price: parseFloat(basePrice.toFixed(2)),
    change: parseFloat((Math.random() * 10 - 5).toFixed(2)),
    change_percent: parseFloat((Math.random() * 5 - 2.5).toFixed(2)),
    volume: Math.floor(Math.random() * 10000000),
    timestamp: new Date().toISOString()
  };
}

function executeSearchTool(args: { query: string; num_results?: number }): any {
  const { query, num_results = 3 } = args;
  const results = [];

  for (let i = 0; i < Math.min(num_results, 3); i++) {
    results.push({
      title: `Result ${i + 1} for "${query}"`,
      url: `https://example.com/result${i + 1}`,
      snippet: `This is a sample search result snippet about ${query}...`
    });
  }

  return {
    query,
    total_results: results.length,
    results
  };
}

function executeCalculatorTool(args: { expression: string }): any {
  try {
    const expr = args.expression
      .replace(/sqrt\(([^)]+)\)/g, 'Math.sqrt($1)')
      .replace(/pow\(([^,]+),([^)]+)\)/g, 'Math.pow($1,$2)');

    if (!/^[\d\s+\-*/().Math]+$/.test(expr)) {
      return { error: 'Invalid expression', expression: args.expression };
    }

    const result = eval(expr);
    return {
      expression: args.expression,
      result,
      formatted: `${args.expression} = ${result}`
    };
  } catch (error) {
    return {
      error: 'Calculation failed',
      expression: args.expression,
      message: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

function executeToolCall(toolName: string, args: any): any {
  switch (toolName) {
    case 'get_weather':
      return executeWeatherTool(args);
    case 'get_stock_price':
      return executeStockTool(args);
    case 'search_web':
      return executeSearchTool(args);
    case 'calculate':
      return executeCalculatorTool(args);
    default:
      return { error: 'Unknown tool', tool: toolName };
  }
}

// ============================================================================
// Streaming Examples
// ============================================================================

async function main() {
  console.log('\n╔═══════════════════════════════════════════════════════════════╗');
  console.log('║      cascadeflow - Streaming with Tools Examples            ║');
  console.log('╚═══════════════════════════════════════════════════════════════╝\n');

  if (!process.env.OPENAI_API_KEY) {
    console.log('⚠️  OPENAI_API_KEY not found in environment');
    console.log('   This example requires OpenAI for streaming tool calls\n');
    return;
  }

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
      enabled: true,
    },
  });

  console.log('🔧 Streaming with tool capabilities:');
  console.log('   • Real-time token streaming');
  console.log('   • Tool call detection');
  console.log('   • Progressive tool execution');
  console.log('   • Multi-step workflows');
  console.log('');

  // ======================================================================
  // Example 1: Simple Tool Call with Streaming
  // ======================================================================
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 1: Weather Query with Streaming');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    console.log('Query: What\'s the weather in Tokyo?\n');

    let toolCallsDetected = 0;
    const toolResults: any[] = [];

    for await (const event of agent.stream(
      "What's the weather like in Tokyo?",
      {
        maxTokens: 200,
        tools: [weatherTool],
      }
    )) {
      if (event.type === StreamEventType.CHUNK) {
        process.stdout.write(event.content);
      } else if (event.type === StreamEventType.TOOL_CALL) {
        toolCallsDetected++;
        const toolData = event.data;
        console.log(`\n\n🔧 Tool Call #${toolCallsDetected}: ${toolData.name}`);
        console.log(`   Arguments: ${JSON.stringify(toolData.arguments, null, 2)}`);

        // Execute tool
        const result = executeToolCall(toolData.name, toolData.arguments);
        toolResults.push(result);
        console.log(`   Result: ${JSON.stringify(result, null, 2)}\n`);
      } else if (event.type === StreamEventType.DRAFT_DECISION) {
        if (event.data.accepted) {
          console.log(`\n✓ Draft accepted (confidence: ${(event.data.confidence * 100).toFixed(0)}%)`);
        } else {
          console.log(`\n⤴️  Cascading to better model (confidence: ${(event.data.confidence * 100).toFixed(0)}%)`);
        }
      } else if (event.type === StreamEventType.COMPLETE) {
        console.log(`\n\n💰 Cost: $${event.data.result.totalCost.toFixed(6)}`);
        console.log(`📊 Model: ${event.data.result.modelUsed}`);
      }
    }

    console.log(`\n✅ Tool calls detected: ${toolCallsDetected}`);
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 2: Multiple Tool Calls
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 2: Stock Price Lookup with Analysis');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    console.log('Query: Get AAPL stock price and analyze the trend\n');

    let toolCount = 0;

    for await (const event of agent.stream(
      "What's the current AAPL stock price?",
      {
        maxTokens: 250,
        tools: [stockTool],
      }
    )) {
      if (event.type === StreamEventType.CHUNK) {
        process.stdout.write(event.content);
      } else if (event.type === StreamEventType.TOOL_CALL) {
        toolCount++;
        const toolData = event.data;
        const result = executeToolCall(toolData.name, toolData.arguments);

        console.log(`\n\n📈 Stock Data Retrieved:`);
        console.log(`   Symbol: ${result.symbol}`);
        console.log(`   Price: $${result.price}`);
        console.log(`   Change: ${result.change >= 0 ? '+' : ''}${result.change} (${result.change_percent}%)`);
        console.log(`   Volume: ${result.volume.toLocaleString()}\n`);
      } else if (event.type === StreamEventType.COMPLETE) {
        console.log(`\n\n💰 Cost: $${event.data.result.totalCost.toFixed(6)}`);
      }
    }
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 3: Complex Multi-Tool Workflow
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 3: Multi-Tool Workflow');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    console.log('Query: Search for TypeScript tutorials and count results\n');

    const toolExecutions: any[] = [];

    for await (const event of agent.stream(
      "Search for TypeScript tutorials",
      {
        maxTokens: 300,
        tools: [searchTool, calculatorTool],
      }
    )) {
      if (event.type === StreamEventType.CHUNK) {
        process.stdout.write(event.content);
      } else if (event.type === StreamEventType.TOOL_CALL) {
        const toolData = event.data;
        const result = executeToolCall(toolData.name, toolData.arguments);
        toolExecutions.push({ tool: toolData.name, result });

        console.log(`\n\n🛠️  ${toolData.name}:`);
        if (toolData.name === 'search_web') {
          console.log(`   Query: "${result.query}"`);
          console.log(`   Found: ${result.total_results} results`);
          result.results.forEach((r: any, idx: number) => {
            console.log(`   ${idx + 1}. ${r.title}`);
          });
        } else if (toolData.name === 'calculate') {
          console.log(`   Expression: ${result.expression}`);
          console.log(`   Result: ${result.result}`);
        }
        console.log('');
      } else if (event.type === StreamEventType.SWITCH) {
        console.log(`\n⤴️  Cascade: ${event.data.fromModel} → ${event.data.toModel}`);
      } else if (event.type === StreamEventType.COMPLETE) {
        console.log(`\n\n✅ Workflow complete`);
        console.log(`📊 Tools used: ${toolExecutions.length}`);
        console.log(`💰 Cost: $${event.data.result.totalCost.toFixed(6)}`);
      }
    }
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Example 4: Streaming Progress Indicators
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Example 4: Progress Tracking');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    console.log('Query: Calculate compound interest\n');

    let chunkCount = 0;
    let startTime = Date.now();

    for await (const event of agent.stream(
      "Calculate compound interest on $1000 at 5% for 10 years: 1000 * pow(1.05, 10)",
      {
        maxTokens: 200,
        tools: [calculatorTool],
      }
    )) {
      if (event.type === StreamEventType.START) {
        console.log('⏱️  Stream started...\n');
      } else if (event.type === StreamEventType.CHUNK) {
        chunkCount++;
        process.stdout.write(event.content);
      } else if (event.type === StreamEventType.TOOL_CALL) {
        const toolData = event.data;
        const result = executeToolCall(toolData.name, toolData.arguments);

        console.log(`\n\n🧮 Calculation:`);
        if (result.error) {
          console.log(`   ⚠️  Error: ${result.error}`);
        } else {
          console.log(`   ${result.formatted}`);
        }
        console.log('');
      } else if (event.type === StreamEventType.COMPLETE) {
        const duration = Date.now() - startTime;
        console.log(`\n\n📊 Stream Statistics:`);
        console.log(`   Chunks: ${chunkCount}`);
        console.log(`   Duration: ${duration}ms`);
        console.log(`   Cost: $${event.data.result.totalCost.toFixed(6)}`);
      }
    }
  } catch (error) {
    console.error('Error:', error instanceof Error ? error.message : error);
  }

  // ======================================================================
  // Summary
  // ======================================================================
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📋 Streaming + Tools Summary');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  console.log('✅ Key Features Demonstrated:');
  console.log('   • Real-time streaming with tool detection');
  console.log('   • TOOL_CALL events during stream');
  console.log('   • Progressive tool execution');
  console.log('   • Multi-tool workflows');
  console.log('   • Stream progress tracking');
  console.log('');
  console.log('🎯 Event Types Used:');
  console.log('   • StreamEventType.START - Stream initialization');
  console.log('   • StreamEventType.CHUNK - Token chunks');
  console.log('   • StreamEventType.TOOL_CALL - Tool invocations');
  console.log('   • StreamEventType.DRAFT_DECISION - Quality checks');
  console.log('   • StreamEventType.SWITCH - Model cascades');
  console.log('   • StreamEventType.COMPLETE - Final results');
  console.log('');
  console.log('💡 Best Practices:');
  console.log('   • Execute tools immediately on TOOL_CALL events');
  console.log('   • Display tool results progressively');
  console.log('   • Track stream metrics for UX');
  console.log('   • Handle errors gracefully');
  console.log('');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
