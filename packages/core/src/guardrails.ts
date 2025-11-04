/**
 * Guardrails for CascadeFlow TypeScript (v0.2.1+)
 *
 * Content moderation and PII detection for production safety.
 */

import { GuardrailsCheck, ModerationResult, PiiMatch, UserProfile } from './types';

/**
 * Guardrail violation error
 */
export class GuardrailViolation extends Error {
  constructor(
    message: string,
    public violations: string[]
  ) {
    super(message);
    this.name = 'GuardrailViolation';
  }
}

/**
 * Content moderator using regex patterns
 *
 * Basic v0.2.1 implementation. For production, consider integrating
 * with OpenAI Moderation API or similar services.
 */
export class ContentModerator {
  private patterns: Record<string, RegExp[]>;

  constructor(strictMode: boolean = false) {
    // Note: strictMode reserved for future use (API integration)
    void strictMode;

    // Compile harmful content patterns
    this.patterns = {
      hate: [
        /\b(hate|despise)\s+(all\s+)?(jews|muslims|christians|blacks|whites|gays|trans)/i,
        /\bgenocide\b/i,
        /\bexterminate\b.*\b(race|religion|ethnicity)/i,
      ],
      violence: [
        /\b(kill|murder|assassinate|torture)\s+(someone|people|them)/i,
        /\bhow\s+to\s+(build|make)\s+(bomb|weapon|explosive)/i,
        /\bshoot\s+up\s+(school|mall|church)/i,
      ],
      'self-harm': [
        /\bhow\s+to\s+(kill|hurt)\s+(myself|yourself)/i,
        /\bsuicide\s+(method|plan|instructions)/i,
        /\bcut\s+(myself|yourself|wrists)/i,
      ],
      sexual: [
        /\bexplicit\s+sexual\s+content/i,
        /\bchild\s+(porn|sexual)/i,
      ],
      harassment: [
        /\bstalk\b.*\bperson/i,
        /\bdox\b.*\bsomeone/i,
      ],
    };
  }

  /**
   * Check text for harmful content
   *
   * @param text - Text to moderate
   * @returns Moderation result
   */
  check(text: string): ModerationResult {
    const violations: string[] = [];
    const categories: string[] = [];

    // Check each category
    for (const [category, patterns] of Object.entries(this.patterns)) {
      for (const pattern of patterns) {
        if (pattern.test(text)) {
          violations.push(`Detected ${category} content`);
          categories.push(category);
          break; // One match per category
        }
      }
    }

    return {
      isSafe: violations.length === 0,
      violations,
      categories,
      confidence: violations.length > 0 ? 0.8 : 1.0,
    };
  }

  /**
   * Async version (for future API integration)
   */
  async checkAsync(text: string): Promise<ModerationResult> {
    return this.check(text);
  }
}

/**
 * PII detector using regex patterns
 *
 * Detects common PII types:
 * - Email addresses
 * - Phone numbers (US format)
 * - Social Security Numbers
 * - Credit cards (with Luhn validation)
 * - IP addresses
 */
export class PiiDetector {
  private emailPattern = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
  private phonePatterns = [
    /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/g,
    /\(\d{3}\)\s*\d{3}[-.]?\d{4}\b/g,
  ];
  private ssnPattern = /\b\d{3}-\d{2}-\d{4}\b/g;
  private ccPatterns = [
    /\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b/g, // 16 digit
    /\b\d{4}[-\s]?\d{6}[-\s]?\d{5}\b/g, // 15 digit (Amex)
  ];
  private ipPattern = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;

  /**
   * Detect PII in text
   *
   * @param text - Text to scan
   * @returns List of PII matches
   */
  detect(text: string): PiiMatch[] {
    const matches: PiiMatch[] = [];

    // Detect emails
    for (const match of text.matchAll(this.emailPattern)) {
      matches.push({
        piiType: 'email',
        value: `${match[0].substring(0, 3)}***@***`,
        position: [match.index!, match.index! + match[0].length],
      });
    }

    // Detect phone numbers
    for (const pattern of this.phonePatterns) {
      for (const match of text.matchAll(pattern)) {
        matches.push({
          piiType: 'phone',
          value: '***-***-****',
          position: [match.index!, match.index! + match[0].length],
        });
      }
    }

    // Detect SSN
    for (const match of text.matchAll(this.ssnPattern)) {
      matches.push({
        piiType: 'ssn',
        value: '***-**-****',
        position: [match.index!, match.index! + match[0].length],
      });
    }

    // Detect credit cards
    for (const pattern of this.ccPatterns) {
      for (const match of text.matchAll(pattern)) {
        const digits = match[0].replace(/[-\s]/g, '');
        if (this.luhnCheck(digits)) {
          matches.push({
            piiType: 'credit_card',
            value: '****-****-****-****',
            position: [match.index!, match.index! + match[0].length],
          });
        }
      }
    }

    // Detect IP addresses
    for (const match of text.matchAll(this.ipPattern)) {
      const parts = match[0].split('.');
      if (parts.every((p) => parseInt(p) >= 0 && parseInt(p) <= 255)) {
        matches.push({
          piiType: 'ip_address',
          value: '***.***.***.***',
          position: [match.index!, match.index! + match[0].length],
        });
      }
    }

    return matches;
  }

  /**
   * Redact PII from text
   *
   * @param text - Text to redact
   * @returns Tuple of [redacted_text, matches]
   */
  redact(text: string): [string, PiiMatch[]] {
    const matches = this.detect(text);

    // Sort by position (reverse order to preserve positions)
    matches.sort((a, b) => b.position[0] - a.position[0]);

    let redacted = text;
    for (const match of matches) {
      const [start, end] = match.position;
      redacted = redacted.substring(0, start) + `[${match.piiType.toUpperCase()}]` + redacted.substring(end);
    }

    return [redacted, matches];
  }

  /**
   * Async version (for future API integration)
   */
  async detectAsync(text: string): Promise<PiiMatch[]> {
    return this.detect(text);
  }

  /**
   * Luhn algorithm for credit card validation
   */
  private luhnCheck(cardNumber: string): boolean {
    const digits = cardNumber.split('').map(Number);
    const oddDigits = digits.filter((_, i) => i % 2 === 0).reverse();
    const evenDigits = digits.filter((_, i) => i % 2 === 1).reverse();

    let checksum = oddDigits.reduce((sum, d) => sum + d, 0);
    for (const d of evenDigits) {
      const doubled = d * 2;
      checksum += doubled > 9 ? doubled - 9 : doubled;
    }

    return checksum % 10 === 0;
  }
}

/**
 * Guardrails manager
 *
 * Coordinates content moderation and PII detection based on user profile.
 *
 * @example
 * ```typescript
 * const manager = new GuardrailsManager();
 * const result = await manager.checkContent('user input', profile);
 *
 * if (!result.isSafe) {
 *   throw new GuardrailViolation('Content blocked', result.violations);
 * }
 * ```
 */
export class GuardrailsManager {
  private contentModerator: ContentModerator;
  private piiDetector: PiiDetector;

  constructor() {
    this.contentModerator = new ContentModerator();
    this.piiDetector = new PiiDetector();
  }

  /**
   * Check content against enabled guardrails
   *
   * @param text - Text to check
   * @param profile - User profile with guardrail settings
   * @returns Guardrails check result
   */
  async checkContent(text: string, profile: UserProfile): Promise<GuardrailsCheck> {
    const violations: string[] = [];
    let moderationResult: ModerationResult | undefined;
    let piiMatches: PiiMatch[] | undefined;

    // Check content moderation if enabled
    if (profile.enableContentModeration) {
      moderationResult = await this.contentModerator.checkAsync(text);
      if (!moderationResult.isSafe) {
        violations.push(...moderationResult.violations);
      }
    }

    // Check PII if enabled
    if (profile.enablePiiDetection) {
      piiMatches = await this.piiDetector.detectAsync(text);
      if (piiMatches.length > 0) {
        const piiTypes = [...new Set(piiMatches.map((m) => m.piiType))];
        violations.push(`PII detected: ${piiTypes.join(', ')}`);
      }
    }

    return {
      isSafe: violations.length === 0,
      contentModeration: moderationResult,
      piiDetected: piiMatches,
      violations,
    };
  }

  /**
   * Redact PII from text (if enabled)
   *
   * @param text - Text to redact
   * @param profile - User profile
   * @returns Tuple of [redacted_text, matches]
   */
  async redactPii(text: string, profile: UserProfile): Promise<[string, PiiMatch[]]> {
    if (!profile.enablePiiDetection) {
      return [text, []];
    }

    return this.piiDetector.redact(text);
  }
}
