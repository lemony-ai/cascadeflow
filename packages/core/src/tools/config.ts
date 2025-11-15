/**
 * Tool Configuration
 *
 * Defines tools that can be called by language models.
 * Provides utilities for schema generation and validation.
 *
 * @example
 * ```typescript
 * const tool = new ToolConfig({
 *   name: 'get_weather',
 *   description: 'Get current weather for a location',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       location: { type: 'string', description: 'City name' },
 *       unit: { type: 'string', enum: ['celsius', 'fahrenheit'] }
 *     },
 *     required: ['location']
 *   },
 *   function: getWeather
 * });
 * ```
 */

/**
 * Function type for tool execution
 */
export type ToolFunction = (...args: any[]) => any | Promise<any>;

/**
 * JSON Schema for tool parameters
 */
export interface ToolParameters {
  type: 'object';
  properties: Record<string, any>;
  required?: string[];
  [key: string]: any;
}

/**
 * Configuration options for creating a tool
 */
export interface ToolConfigOptions {
  /** Tool name (must be unique) */
  name: string;

  /** Human-readable description of what the tool does */
  description: string;

  /** JSON Schema for tool parameters */
  parameters: ToolParameters;

  /** Optional function to execute when tool is called */
  function?: ToolFunction;
}

/**
 * Universal tool configuration that works across all providers
 *
 * ToolConfig defines a tool that language models can call.
 * It includes the tool's name, description, parameter schema,
 * and optional execution function.
 *
 * Key features:
 * - Provider-agnostic format
 * - JSON Schema-based parameters
 * - Optional function execution
 * - Automatic validation
 * - Schema generation helpers
 *
 * @example Basic tool
 * ```typescript
 * const weatherTool = new ToolConfig({
 *   name: 'get_weather',
 *   description: 'Get current weather',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       location: { type: 'string', description: 'City name' }
 *     },
 *     required: ['location']
 *   },
 *   function: async (location: string) => {
 *     // Fetch weather data
 *     return { temp: 72, condition: 'sunny' };
 *   }
 * });
 * ```
 *
 * @example From function with manual schema
 * ```typescript
 * function calculate(x: number, y: number): number {
 *   return x + y;
 * }
 *
 * const calcTool = ToolConfig.fromFunction(calculate, {
 *   description: 'Add two numbers',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       x: { type: 'number', description: 'First number' },
 *       y: { type: 'number', description: 'Second number' }
 *     },
 *     required: ['x', 'y']
 *   }
 * });
 * ```
 */
export class ToolConfig {
  /** Tool name (must be unique) */
  readonly name: string;

  /** Human-readable description */
  readonly description: string;

  /** JSON Schema for parameters */
  readonly parameters: ToolParameters;

  /** Optional execution function */
  readonly function?: ToolFunction;

  /**
   * Create a new tool configuration
   *
   * @param options - Tool configuration options
   * @throws {Error} When validation fails
   */
  constructor(options: ToolConfigOptions) {
    this.name = options.name;
    this.description = options.description;
    this.parameters = options.parameters;
    this.function = options.function;

    // Validate configuration
    this.validate();
  }

  /**
   * Validate tool configuration
   *
   * Ensures:
   * - Name is not empty
   * - Description is not empty
   * - Parameters is a valid JSON schema object
   *
   * @throws {Error} When validation fails
   */
  private validate(): void {
    if (!this.name || this.name.trim() === '') {
      throw new Error('Tool name cannot be empty');
    }

    if (!this.description || this.description.trim() === '') {
      throw new Error('Tool description cannot be empty');
    }

    if (!this.parameters || typeof this.parameters !== 'object') {
      throw new Error('Tool parameters must be a dictionary (JSON schema)');
    }

    if (this.parameters.type !== 'object') {
      throw new Error("Tool parameters must be a JSON schema with type='object'");
    }

    if (!this.parameters.properties || typeof this.parameters.properties !== 'object') {
      throw new Error('Tool parameters must have a properties object');
    }
  }

  /**
   * Create ToolConfig from a function with manual schema
   *
   * Note: TypeScript doesn't support runtime type introspection,
   * so you must provide the parameter schema manually.
   *
   * @param func - Function to wrap
   * @param options - Configuration options (description and parameters required)
   * @returns ToolConfig instance
   *
   * @example
   * ```typescript
   * function getWeather(city: string, unit?: string): Promise<object> {
   *   // Implementation
   *   return Promise.resolve({ temp: 72, condition: 'sunny' });
   * }
   *
   * const tool = ToolConfig.fromFunction(getWeather, {
   *   description: 'Get weather for a city',
   *   parameters: {
   *     type: 'object',
   *     properties: {
   *       city: { type: 'string', description: 'City name' },
   *       unit: { type: 'string', enum: ['celsius', 'fahrenheit'], description: 'Temperature unit' }
   *     },
   *     required: ['city']
   *   }
   * });
   * ```
   */
  static fromFunction(
    func: ToolFunction,
    options: {
      description: string;
      parameters: ToolParameters;
      name?: string;
    }
  ): ToolConfig {
    const name = options.name || func.name;

    if (!name) {
      throw new Error('Function must have a name or you must provide a name option');
    }

    return new ToolConfig({
      name,
      description: options.description,
      parameters: options.parameters,
      function: func,
    });
  }

  /**
   * Convert to OpenAI function calling format
   *
   * @returns OpenAI-compatible tool definition
   *
   * @example
   * ```typescript
   * const tool = new ToolConfig({...});
   * const openaiFormat = tool.toOpenAIFormat();
   * // { type: 'function', function: { name: '...', description: '...', parameters: {...} } }
   * ```
   */
  toOpenAIFormat(): {
    type: 'function';
    function: {
      name: string;
      description: string;
      parameters: ToolParameters;
    };
  } {
    return {
      type: 'function',
      function: {
        name: this.name,
        description: this.description,
        parameters: this.parameters,
      },
    };
  }

  /**
   * Convert to Anthropic tool format
   *
   * @returns Anthropic-compatible tool definition
   *
   * @example
   * ```typescript
   * const tool = new ToolConfig({...});
   * const anthropicFormat = tool.toAnthropicFormat();
   * // { name: '...', description: '...', input_schema: {...} }
   * ```
   */
  toAnthropicFormat(): {
    name: string;
    description: string;
    input_schema: ToolParameters;
  } {
    return {
      name: this.name,
      description: this.description,
      input_schema: this.parameters,
    };
  }

  /**
   * Convert to universal format
   *
   * This is the standard format used throughout cascadeflow.
   * It's provider-agnostic and can be converted to any provider format.
   *
   * @returns Universal tool definition
   *
   * @example
   * ```typescript
   * const tool = new ToolConfig({...});
   * const universalFormat = tool.toUniversalFormat();
   * // { name: '...', description: '...', parameters: {...} }
   * ```
   */
  toUniversalFormat(): {
    name: string;
    description: string;
    parameters: ToolParameters;
  } {
    return {
      name: this.name,
      description: this.description,
      parameters: this.parameters,
    };
  }

  /**
   * Create a copy of this tool config
   *
   * @returns New ToolConfig instance with same properties
   */
  clone(): ToolConfig {
    return new ToolConfig({
      name: this.name,
      description: this.description,
      parameters: JSON.parse(JSON.stringify(this.parameters)),
      function: this.function,
    });
  }

  /**
   * Get JSON representation
   *
   * @returns JSON-serializable object (excludes function)
   */
  toJSON(): {
    name: string;
    description: string;
    parameters: ToolParameters;
  } {
    return {
      name: this.name,
      description: this.description,
      parameters: this.parameters,
    };
  }
}

/**
 * Create a tool configuration (convenience function)
 *
 * Alias for `new ToolConfig(options)`
 *
 * @param options - Tool configuration options
 * @returns ToolConfig instance
 *
 * @example
 * ```typescript
 * const tool = createTool({
 *   name: 'search',
 *   description: 'Search the web',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       query: { type: 'string', description: 'Search query' }
 *     },
 *     required: ['query']
 *   }
 * });
 * ```
 */
export function createTool(options: ToolConfigOptions): ToolConfig {
  return new ToolConfig(options);
}

/**
 * Decorator to create a tool from a function
 *
 * Note: Due to TypeScript limitations, you must provide the schema manually.
 *
 * @param options - Tool configuration (description and parameters required)
 * @returns Decorator function
 *
 * @example
 * ```typescript
 * const getWeatherTool = tool({
 *   description: 'Get weather for a city',
 *   parameters: {
 *     type: 'object',
 *     properties: {
 *       city: { type: 'string', description: 'City name' }
 *     },
 *     required: ['city']
 *   }
 * })(getWeather);
 * ```
 */
export function tool(options: {
  description: string;
  parameters: ToolParameters;
  name?: string;
}): (func: ToolFunction) => ToolConfig {
  return (func: ToolFunction) => {
    return ToolConfig.fromFunction(func, options);
  };
}

/**
 * Infer JSON Schema type from TypeScript type (helper for manual schema creation)
 *
 * Note: This is a runtime helper for building schemas manually.
 * TypeScript doesn't support runtime type introspection.
 *
 * @param value - Sample value to infer type from
 * @returns JSON Schema type string
 *
 * @example
 * ```typescript
 * inferJsonType(42);        // 'integer'
 * inferJsonType(3.14);      // 'number'
 * inferJsonType('hello');   // 'string'
 * inferJsonType(true);      // 'boolean'
 * inferJsonType([1, 2, 3]); // 'array'
 * inferJsonType({ a: 1 });  // 'object'
 * ```
 */
export function inferJsonType(value: any): string {
  if (value === null || value === undefined) {
    return 'string';
  }

  const type = typeof value;

  switch (type) {
    case 'number':
      return Number.isInteger(value) ? 'integer' : 'number';
    case 'string':
      return 'string';
    case 'boolean':
      return 'boolean';
    case 'object':
      return Array.isArray(value) ? 'array' : 'object';
    default:
      return 'string';
  }
}

/**
 * Build a simple parameter schema (helper for manual schema creation)
 *
 * @param properties - Property definitions
 * @param required - Required property names
 * @returns JSON Schema object
 *
 * @example
 * ```typescript
 * const schema = buildParameterSchema({
 *   city: { type: 'string', description: 'City name' },
 *   unit: { type: 'string', enum: ['C', 'F'], description: 'Temperature unit' }
 * }, ['city']);
 * // Returns: { type: 'object', properties: {...}, required: ['city'] }
 * ```
 */
export function buildParameterSchema(
  properties: Record<string, any>,
  required?: string[]
): ToolParameters {
  const schema: ToolParameters = {
    type: 'object',
    properties,
  };

  if (required && required.length > 0) {
    schema.required = required;
  }

  return schema;
}
