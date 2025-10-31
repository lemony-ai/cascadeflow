# Reasoning Models Specification

This document outlines all supported reasoning models across providers and their specific API requirements.

## Provider Support Matrix

| Provider | Models | Auto-Detection | Special Parameters | Thinking Tokens |
|----------|--------|----------------|-------------------|-----------------|
| OpenAI | o1-preview, o1-mini, o1-2024-12-17, o1, o3-mini | ✅ Yes | reasoning_effort, max_completion_tokens | ✅ Yes |
| Anthropic | claude-3-7-sonnet | ✅ Yes | thinking (budget_tokens) | ✅ Yes |
| Ollama | deepseek-r1 (all sizes) | ✅ Yes | None | ⚠️ Model-dependent |
| vLLM | deepseek-r1 (all sizes) | ✅ Yes | None | ⚠️ Model-dependent |
| LiteLLM | All above via routing | ✅ Yes | Provider-specific | ✅ Yes |

## OpenAI Reasoning Models

### Supported Models:
- `o1-preview` - Original reasoning model
- `o1-mini` - Smaller, faster reasoning model
- `o1-2024-12-17` - Latest o1 with reasoning_effort
- `o1` - Base o1 model
- `o3-mini` - Next-gen reasoning model

### Capabilities:
```typescript
{
  o1-preview: {
    supportsStreaming: true,
    supportsTools: false,
    supportsSystemMessages: false,
    supportsReasoningEffort: false,
    requiresMaxCompletionTokens: false
  },
  o1-2024-12-17: {
    supportsStreaming: false,
    supportsTools: false,
    supportsSystemMessages: false,
    supportsReasoningEffort: true,
    requiresMaxCompletionTokens: true
  },
  o3-mini: {
    supportsStreaming: true,
    supportsTools: true,
    supportsSystemMessages: false,
    supportsReasoningEffort: true,
    requiresMaxCompletionTokens: true
  }
}
```

### API Parameters:
- `max_completion_tokens` (instead of max_tokens for some models)
- `reasoning_effort`: "low" | "medium" | "high" (for o1-2024-12-17, o1, o3-mini)

### Response Format:
```json
{
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 200,
    "total_tokens": 300,
    "completion_tokens_details": {
      "reasoning_tokens": 50
    }
  }
}
```

### Pricing (per 1M tokens):
- o1-preview: $15 input, $60 output
- o1-mini: $3 input, $12 output
- o1-2024-12-17: $15 input, $60 output
- o1: $15 input, $60 output
- o3-mini: $1 input, $5 output

## Anthropic Claude Extended Thinking

### Supported Models:
- `claude-3-7-sonnet` - Hybrid reasoning model

### Capabilities:
```typescript
{
  'claude-3-7-sonnet': {
    supportsStreaming: true,
    supportsTools: true,
    supportsSystemMessages: true,
    supportsExtendedThinking: true,
    requiresThinkingBudget: true
  }
}
```

### API Parameters:
```json
{
  "thinking": {
    "type": "enabled",
    "budget_tokens": 2000  // Minimum 1024
  }
}
```

### Response Format:
```json
{
  "content": [
    {
      "type": "thinking",
      "thinking": "Step-by-step reasoning process...",
      "signature": "optional_signature"
    },
    {
      "type": "text",
      "text": "Final answer..."
    }
  ]
}
```

### Pricing (per 1M tokens):
- claude-3-7-sonnet: $3 input, $15 output (thinking tokens included in output)

## DeepSeek-R1 Models (Ollama/vLLM)

### Supported Models:
- `deepseek-r1:1.5b` - Ultra-small reasoning
- `deepseek-r1:8b` - Balanced reasoning
- `deepseek-r1:70b` - Large reasoning
- `deepseek-r1:671b` - Full-scale reasoning
- `deepseek-r1-0528:*` - Latest version

### Capabilities:
```typescript
{
  'deepseek-r1': {
    supportsStreaming: true,
    supportsTools: true,
    supportsSystemMessages: true,
    requiresSpecialHandling: false  // Standard model interface
  }
}
```

### API Parameters:
- Uses standard Ollama/vLLM parameters
- No special reasoning parameters needed
- Model handles reasoning internally

### Detection Pattern:
```typescript
function isDeepSeekR1(modelName: string): boolean {
  const name = modelName.toLowerCase();
  return name.includes('deepseek-r1') || name.includes('deepseek-r1-0528');
}
```

### Pricing:
- Self-hosted, no API costs
- Hardware costs only

## LiteLLM Integration

### Router Configuration:
```python
{
  "model_list": [
    {
      "model_name": "reasoning-model",
      "litellm_params": {
        "model": "o1-mini",
        "reasoning_effort": "high"
      }
    },
    {
      "model_name": "reasoning-model",
      "litellm_params": {
        "model": "claude-3-7-sonnet",
        "thinking": {"type": "enabled", "budget_tokens": 2000}
      }
    }
  ]
}
```

### Auto-Detection Strategy:
1. Check if LiteLLM is available
2. If available, use LiteLLM's routing
3. If not available, use built-in provider detection
4. Fallback to standard model handling

## Implementation Strategy

### 1. TypeScript Base Types
```typescript
// Extend existing types
interface ReasoningModelInfo {
  isReasoning: boolean;
  provider: 'openai' | 'anthropic' | 'ollama' | 'vllm';
  supportsStreaming: boolean;
  supportsTools: boolean;
  supportsSystemMessages: boolean;
  supportsReasoningEffort?: boolean;
  supportsExtendedThinking?: boolean;
  requiresMaxCompletionTokens?: boolean;
  requiresThinkingBudget?: boolean;
}
```

### 2. Provider-Specific Detection
Each provider implements:
```typescript
function getReasoningModelInfo(modelName: string): ReasoningModelInfo
```

### 3. Unified Request Handling
```typescript
// Auto-configure based on model info
if (modelInfo.supportsReasoningEffort && request.extra?.reasoning_effort) {
  payload.reasoning_effort = request.extra.reasoning_effort;
}

if (modelInfo.supportsExtendedThinking && request.extra?.thinking) {
  payload.thinking = request.extra.thinking;
}
```

### 4. Response Parsing
```typescript
// Extract thinking from response
if (modelInfo.provider === 'anthropic') {
  const thinkingBlock = findThinkingBlock(response.content);
  metadata.thinking = thinkingBlock?.thinking;
}

if (modelInfo.provider === 'openai') {
  metadata.reasoning_tokens = response.usage?.completion_tokens_details?.reasoning_tokens;
}
```

## Testing Requirements

### Unit Tests (per provider):
- Model detection accuracy
- Parameter configuration
- Cost calculation
- Response parsing
- Backward compatibility

### Integration Tests:
- Cross-provider reasoning cascades
- LiteLLM fallback behavior
- n8n node functionality
- Error handling

### Example Test Cases:
```typescript
// OpenAI
test('o1-mini auto-configures reasoning_effort', ...)
test('o3-mini supports tools', ...)

// Anthropic
test('claude-3-7-sonnet extracts thinking blocks', ...)
test('thinking budget validation', ...)

// DeepSeek-R1
test('deepseek-r1:8b detected for ollama', ...)
test('deepseek-r1-0528 detected for vllm', ...)
```

## Migration Path

### Phase 1: Core Types (Current)
- ✅ OpenAI types and detection
- ✅ Basic Anthropic thinking types
- 🔄 DeepSeek detection types

### Phase 2: Provider Implementation
- ✅ OpenAI provider (complete)
- 🔄 Anthropic provider (extend)
- 🔄 Ollama provider (add DeepSeek)
- 🔄 vLLM provider (add DeepSeek)

### Phase 3: Integration
- 🔄 LiteLLM wrapper
- 🔄 n8n nodes
- 🔄 Examples
- 🔄 Documentation

## Success Criteria

✅ Zero-configuration for all reasoning models
✅ Automatic parameter handling
✅ Accurate cost tracking
✅ Comprehensive test coverage (>90%)
✅ Backward compatible
✅ Cross-provider cascade support
✅ Documentation complete

## Notes

- All reasoning models should work without special configuration
- Developers just specify model name, everything else is automatic
- Cost tracking must include reasoning/thinking tokens
- Fallback to standard behavior if detection fails
- LiteLLM integration optional but leveraged when available
