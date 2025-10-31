# LiteLLM Provider Integration Example

**File:** [`litellm_providers.py`](litellm_providers.py)

Complete example showing how to use LiteLLM integration for cost tracking and accessing additional providers like DeepSeek, Google Gemini, Azure OpenAI, and more.

---

## What's Included

This example contains **8 complete demonstrations**:

### ✅ Example 1: Supported Providers
Lists all 10 providers supported via LiteLLM integration with their value propositions.

### ✅ Example 2: Cost Calculation
Compares costs across OpenAI, Anthropic, DeepSeek, and Google for the same task.

### ✅ Example 3: Model Pricing Details
Shows detailed per-token pricing information for different models.

### ✅ Example 4: Cost Comparison Across Use Cases
Compares costs for simple queries, medium tasks, complex tasks, and large documents.

### ✅ Example 5: Provider Information
Dynamically retrieves provider capabilities and configuration requirements.

### ✅ Example 6: Convenience Functions
Quick cost calculations without creating provider instances.

### ✅ Example 7: API Key Status
Checks which API keys are configured in your environment.

### ✅ Example 8: Real-World Usage
Shows how to integrate LiteLLM with CascadeAgent for actual cascades.

---

## Quick Start

```bash
# Install dependencies (if not already installed)
pip install cascadeflow[all]

# Run the example (no API keys required for cost info)
python examples/integrations/litellm_providers.py
```

---

## Example Output

```
🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯
  LiteLLM Provider Integration Examples
🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯

================================================================================
  Example 2: Cost Calculation with LiteLLM
================================================================================

Cost comparison for 1K input + 500 output tokens:

  OpenAI          gpt-4o                    $0.007500
  Anthropic       anthropic/claude-3-5-sonnet-20241022 $0.010500
  DeepSeek        deepseek/deepseek-coder   $0.000280
  Google          gemini/gemini-1.5-flash   $0.000225

💡 TIP: LiteLLM automatically updates pricing - no manual updates needed!

================================================================================
  Example 4: Cost Comparison Across Use Cases
================================================================================

Cost comparison across different use cases:

Use Case                      Tokens       GPT-4o    GPT-4o-mini    Gemini Flash
--------------------------------------------------------------------------------
Simple query                  100+50 $   0.000750 $     0.000045 $      0.000007
Medium task                  500+250 $   0.003750 $     0.000225 $      0.000037
Complex task               2000+1000 $   0.015000 $     0.000900 $      0.000150
Large document            10000+5000 $   0.075000 $     0.004500 $      0.000750

💡 INSIGHTS:
  - GPT-4o-mini is ~30x cheaper than GPT-4o
  - Gemini Flash is ~100x cheaper than GPT-4o
  - Use cascading to get quality at lower cost!
```

---

## Supported Providers

Through LiteLLM, you can access:

| Provider | Value Proposition | Example Models | Cost Savings |
|----------|-------------------|----------------|--------------|
| **OpenAI** | Industry standard | gpt-4o, gpt-4o-mini | Baseline |
| **Anthropic** | Best reasoning | claude-3-5-sonnet | Similar |
| **DeepSeek** | Code specialization | deepseek-coder | **95%** vs GPT-4 |
| **Google** | Ultra-cheap | gemini-1.5-flash | **98%** vs GPT-4o |
| **Azure** | Enterprise compliance | azure/gpt-4 | Same as OpenAI |
| **Groq** | Ultra-fast | llama-3.1-70b | 90% vs GPT-4 |
| **Together** | Open models | llama-3-70b | 85% vs GPT-4 |
| **Fireworks** | Fast inference | llama-v3-70b | 80% vs GPT-4 |
| **Cohere** | Search/RAG | command | 70% vs GPT-4 |
| **Ollama** | Local/free | llama3, mistral | **100%** (free) |

---

## Usage Examples

### 1. Get Provider Information

```python
from cascadeflow.integrations.litellm import get_provider_info

info = get_provider_info("deepseek")
print(f"Value: {info.value_prop}")
# Output: "Specialized code models, very cost-effective for coding tasks"

print(f"Models: {info.example_models}")
# Output: ['deepseek-coder', 'deepseek-chat']
```

### 2. Calculate Costs

```python
from cascadeflow.integrations.litellm import calculate_cost

# DeepSeek cost (use provider prefix for accurate pricing)
cost = calculate_cost(
    model="deepseek/deepseek-coder",
    input_tokens=1000,
    output_tokens=500
)
print(f"DeepSeek cost: ${cost:.6f}")
# Output: DeepSeek cost: $0.000280

# Compare to GPT-4
gpt4_cost = calculate_cost(
    model="gpt-4o",
    input_tokens=1000,
    output_tokens=500
)
print(f"GPT-4o cost: ${gpt4_cost:.6f}")
# Output: GPT-4o cost: $0.007500

# Savings
savings = ((gpt4_cost - cost) / gpt4_cost) * 100
print(f"Savings: {savings:.1f}%")
# Output: Savings: 96.3%
```

**💡 TIP:** Use provider prefixes (e.g., `deepseek/deepseek-coder`, `anthropic/claude-3-5-sonnet-20241022`, `gemini/gemini-1.5-flash`) for accurate LiteLLM pricing.

### 3. Use with CascadeAgent (DeepSeek)

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.integrations.litellm import calculate_cost

# Calculate cost (use provider prefix)
deepseek_cost = calculate_cost(
    model="deepseek/deepseek-coder",
    input_tokens=1000,
    output_tokens=1000
)

# Create cascade with DeepSeek
agent = CascadeAgent(models=[
    ModelConfig(
        name="deepseek-coder",
        provider="openai",  # DeepSeek uses OpenAI-compatible API
        cost=deepseek_cost * 1000,  # Convert to per-1K token cost
        base_url="https://api.deepseek.com/v1"
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.00625
    )
])

# Run query (95% cheaper than using GPT-4 alone!)
result = await agent.run("Write a Python function to merge sorted lists")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Model: {result.model_used}")
```

### 4. Use with CascadeAgent (Google Gemini)

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.integrations.litellm import calculate_cost

# Calculate cost (use provider prefix)
gemini_cost = calculate_cost(
    model="gemini/gemini-1.5-flash",
    input_tokens=1000,
    output_tokens=1000
)

# Create cascade with Gemini (97% cheaper than GPT-4o!)
agent = CascadeAgent(models=[
    ModelConfig(
        name="gemini-1.5-flash",
        provider="openai",  # Use generic provider
        cost=gemini_cost * 1000,
        base_url="https://generativelanguage.googleapis.com/v1beta"
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.00625
    )
])

result = await agent.run("Summarize this text: ...")
```

### 5. List All Providers

```python
from cascadeflow.integrations.litellm import SUPPORTED_PROVIDERS

for name, info in SUPPORTED_PROVIDERS.items():
    print(f"{info.display_name}: {info.value_prop}")
```

**Output:**
```
OpenAI: Industry-leading quality, most reliable, best for production
Anthropic Claude: Best for reasoning and analysis, strong safety features
Groq: Fastest inference speed, ultra-low latency, free tier
DeepSeek: Specialized code models, very cost-effective for coding tasks
Google (Vertex AI): Enterprise integration, GCP ecosystem, Gemini models
...
```

---

## API Keys (Optional)

The example runs without API keys and shows cost information. To test actual API calls:

```bash
# DeepSeek (5-10x cheaper for code)
export DEEPSEEK_API_KEY="sk-..."

# Google/Vertex AI (50-100x cheaper for simple tasks)
export GOOGLE_API_KEY="..."

# Azure OpenAI (enterprise compliance)
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://your-resource.openai.azure.com"
```

---

## Cost Savings Examples

### Scenario 1: Code Generation
- **Task:** Generate Python functions
- **Before:** GPT-4 @ $0.03/1K tokens
- **After:** DeepSeek @ $0.00028/1K tokens
- **Savings:** 99% (**~$29.70 saved per $30 spent**)

### Scenario 2: Simple Questions
- **Task:** Answer simple queries
- **Before:** GPT-4o @ $0.0075/1K tokens
- **After:** Gemini Flash @ $0.000225/1K tokens
- **Savings:** 97% (**~$7.27 saved per $7.50 spent**)

### Scenario 3: Smart Cascading
- **Task:** Mixed complexity queries
- **Approach:** Gemini → DeepSeek → GPT-4o cascade
- **Average Savings:** 70-90%

**Annual Impact:** For 1M tokens/month:
- GPT-4 only: $30,000/year
- With DeepSeek/Gemini: $1,500-$9,000/year
- **Savings: $21,000-$28,500/year**

---

## Documentation

### Related Guides
- **Provider Guide:** [docs/guides/providers.md](../../docs/guides/providers.md)
- **Cost Tracking:** [docs/guides/cost_tracking.md](../../docs/guides/cost_tracking.md)

### Source Code
- **LiteLLM Integration:** [cascadeflow/integrations/litellm.py](../../cascadeflow/integrations/litellm.py)
- **Example Code:** [litellm_providers.py](litellm_providers.py)

### External Resources
- **LiteLLM Docs:** https://docs.litellm.ai/docs/providers
- **DeepSeek Docs:** https://platform.deepseek.com/docs
- **Google AI Docs:** https://ai.google.dev/docs

---

## Troubleshooting

### Provider Prefixes for Accurate Pricing

**IMPORTANT:** Always use provider prefixes for accurate pricing:

- ✅ `deepseek/deepseek-coder` (not `deepseek-coder`)
- ✅ `anthropic/claude-3-5-sonnet-20241022` (not `claude-3-5-sonnet`)
- ✅ `gemini/gemini-1.5-flash` (not `gemini-1.5-flash`)

This ensures LiteLLM correctly identifies the model and returns accurate pricing from its database. Without prefixes, CascadeFlow will derive pricing using `completion_cost()`, which still works but may show debug messages.

### "API key not found"
The example works without API keys for cost calculations. API keys are only needed for actual API calls.

### "Import error: No module named litellm"
Install LiteLLM:
```bash
pip install litellm
# Or
pip install cascadeflow[all]  # Includes LiteLLM
```

---

## Summary

This example shows you how to:
- ✅ Access 10+ providers via LiteLLM
- ✅ Calculate accurate costs
- ✅ Compare costs across providers
- ✅ Integrate with CascadeAgent
- ✅ Save 70-98% on AI costs

**Run it now:**
```bash
python examples/integrations/litellm_providers.py
```

---

**💰 Start saving on AI costs today!** 🚀
