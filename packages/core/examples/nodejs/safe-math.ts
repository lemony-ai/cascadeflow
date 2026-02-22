/**
 * Safe arithmetic evaluator for examples.
 *
 * Supported:
 * - Binary operators: +, -, *, /
 * - Parentheses
 * - Unary + and -
 * - Functions: sqrt(x), abs(x), pow(x, y)
 */

type MathFn = (args: number[]) => number;

const FUNCTIONS: Record<string, MathFn> = {
  sqrt: (args) => {
    if (args.length !== 1) {
      throw new Error('sqrt() expects exactly 1 argument');
    }
    return Math.sqrt(args[0]);
  },
  abs: (args) => {
    if (args.length !== 1) {
      throw new Error('abs() expects exactly 1 argument');
    }
    return Math.abs(args[0]);
  },
  pow: (args) => {
    if (args.length !== 2) {
      throw new Error('pow() expects exactly 2 arguments');
    }
    return Math.pow(args[0], args[1]);
  },
};

function tokenize(expression: string): string[] {
  const tokens: string[] = [];
  const pattern = /\s*([A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|\.\d+|[()+\-*/,])\s*/gy;
  let cursor = 0;

  while (cursor < expression.length) {
    pattern.lastIndex = cursor;
    const match = pattern.exec(expression);
    if (!match) {
      throw new Error(`Invalid token near "${expression.slice(cursor, cursor + 12)}"`);
    }
    tokens.push(match[1]);
    cursor = pattern.lastIndex;
  }

  return tokens;
}

class MathParser {
  private readonly tokens: string[];
  private index = 0;

  constructor(expression: string) {
    this.tokens = tokenize(expression);
  }

  parse(): number {
    const value = this.parseExpression();
    if (!this.isAtEnd()) {
      throw new Error(`Unexpected token "${this.peek()}"`);
    }
    return value;
  }

  private parseExpression(): number {
    let value = this.parseTerm();
    while (this.peek() === '+' || this.peek() === '-') {
      const operator = this.consume();
      const right = this.parseTerm();
      value = operator === '+' ? value + right : value - right;
    }
    return value;
  }

  private parseTerm(): number {
    let value = this.parseFactor();
    while (this.peek() === '*' || this.peek() === '/') {
      const operator = this.consume();
      const right = this.parseFactor();
      if (operator === '/') {
        if (right === 0) {
          throw new Error('Division by zero');
        }
        value /= right;
      } else {
        value *= right;
      }
    }
    return value;
  }

  private parseFactor(): number {
    const token = this.peek();
    if (!token) {
      throw new Error('Unexpected end of expression');
    }

    if (token === '+' || token === '-') {
      const operator = this.consume();
      const value = this.parseFactor();
      return operator === '-' ? -value : value;
    }

    if (token === '(') {
      this.consume(); // (
      const value = this.parseExpression();
      this.expect(')');
      return value;
    }

    if (/^\d+(?:\.\d+)?$/.test(token) || /^\.\d+$/.test(token)) {
      const numberToken = this.consume();
      const value = Number(numberToken);
      if (!Number.isFinite(value)) {
        throw new Error('Invalid numeric value');
      }
      return value;
    }

    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(token)) {
      const name = this.consume();
      const fn = FUNCTIONS[name];
      if (!fn) {
        throw new Error(`Unsupported function "${name}"`);
      }
      this.expect('(');
      const args: number[] = [];
      if (this.peek() !== ')') {
        args.push(this.parseExpression());
        while (this.peek() === ',') {
          this.consume();
          args.push(this.parseExpression());
        }
      }
      this.expect(')');
      const value = fn(args);
      if (!Number.isFinite(value)) {
        throw new Error(`Function "${name}" returned a non-finite value`);
      }
      return value;
    }

    throw new Error(`Unexpected token "${token}"`);
  }

  private peek(): string | undefined {
    return this.tokens[this.index];
  }

  private consume(): string {
    const token = this.tokens[this.index];
    this.index += 1;
    return token;
  }

  private expect(expected: string): void {
    const actual = this.consume();
    if (actual !== expected) {
      throw new Error(`Expected "${expected}" but received "${actual ?? 'end of input'}"`);
    }
  }

  private isAtEnd(): boolean {
    return this.index >= this.tokens.length;
  }
}

export function safeCalculateExpression(expression: string): number {
  const trimmed = expression.trim();
  if (!trimmed) {
    throw new Error('Expression is required');
  }
  if (trimmed.length > 200) {
    throw new Error('Expression is too long');
  }
  return new MathParser(trimmed).parse();
}

