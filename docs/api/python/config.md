# ModelConfig & Configuration (Python)

Configuration classes for cascadeflow models and cascade behavior.

## Class: `ModelConfig`

Configuration for a single model in the cascade.

```python
from cascadeflow import ModelConfig
```

### Constructor

```python
ModelConfig(
    name: str,
    provider: str,
    cost: float,
    keywords: List[str] = [],
    domains: List[str] = [],
    max_tokens: int = 4096,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    extra: Dict[str, Any] = {},
    speed_ms: int = 1000,
    quality_score: float = 0.7,
    supports_tools: bool = True
)
```

### Required Parameters

- `name` (`str`): Model name (e.g., "gpt-4o-mini", "claude-3-5-sonnet")
- `provider` (`str`): Provider name ("openai", "anthropic", "groq", "ollama", "vllm", "together", "huggingface")
- `cost` (`float`): Cost per 1K tokens in USD

### Optional Parameters

- `keywords` (`List[str]`): Keywords for routing (e.g., ["code", "python"])
- `domains` (`List[str]`): Domain specializations (e.g., ["code", "math"])
- `max_tokens` (`int`): Maximum tokens for generation (default: 4096)
- `system_prompt` (`str`): System prompt override
- `temperature` (`float`): Temperature 0-2 (default: 0.7)
- `api_key` (`str`): API key (defaults to environment variable)
- `base_url` (`str`): Custom base URL for vLLM, Ollama, etc.
- `extra` (`Dict`): Provider-specific options
- `speed_ms` (`int`): Expected latency in milliseconds (default: 1000)
- `quality_score` (`float`): Base quality score 0-1 (default: 0.7)
- `supports_tools` (`bool`): Whether model supports function calling (default: True)

### Examples

**Basic Configuration:**
```python
model = ModelConfig(
    name="gpt-4o-mini",
    provider="openai",
    cost=0.00015
)
```

**With All Options:**
```python
model = ModelConfig(
    name="gpt-4o",
    provider="openai",
    cost=0.00625,
    max_tokens=8192,
    temperature=0.3,
    system_prompt="You are a helpful assistant",
    keywords=["general", "chat"],
    domains=["qa", "chat"],
    api_key="sk-...",  # Or use OPENAI_API_KEY env var
    extra={"top_p": 0.9, "frequency_penalty": 0.0}
)
```

**Domain-Specific Model:**
```python
code_model = ModelConfig(
    name="gpt-4o",
    provider="openai",
    cost=0.00625,
    domains=["code", "programming"],
    keywords=["python", "javascript", "typescript"],
    temperature=0.1  # Lower temp for code generation
)
```

**Local Model (vLLM):**
```python
local_model = ModelConfig(
    name="llama-3.1-8b",
    provider="vllm",
    cost=0.0,  # Free (local)
    base_url="http://localhost:8000",
    max_tokens=2048
)
```

---

## Class: `QualityConfig`

Quality validation configuration.

```python
from cascadeflow import QualityConfig
```

### Constructor

```python
QualityConfig(
    threshold: float = 0.7,
    confidence_thresholds: Optional[Dict[str, float]] = None,
    require_minimum_tokens: int = 10,
    require_validation: bool = True,
    enable_adaptive: bool = True
)
```

### Parameters

- `threshold` (`float`): Minimum confidence 0-1 (default: 0.7)
- `confidence_thresholds` (`Dict[str, float]`): Thresholds by complexity level
- `require_minimum_tokens` (`int`): Minimum response length (default: 10)
- `require_validation` (`bool`): Enable validation (default: True)
- `enable_adaptive` (`bool`): Adaptive thresholds by complexity (default: True)

### Examples

**Basic Quality Config:**
```python
quality = QualityConfig(
    threshold=0.8,  # Stricter (more escalations)
    require_minimum_tokens=20
)
```

**Adaptive Thresholds:**
```python
quality = QualityConfig(
    confidence_thresholds={
        "simple": 0.6,    # Lower bar for simple queries
        "moderate": 0.7,  # Medium bar
        "complex": 0.8,   # High bar for complex queries
        "expert": 0.9     # Very high bar
    },
    enable_adaptive=True
)
```

---

## Class: `CascadeConfig`

Advanced cascade behavior configuration.

```python
from cascadeflow import CascadeConfig
```

### Constructor

```python
CascadeConfig(
    quality: Optional[QualityConfig] = None,
    max_budget: Optional[float] = None,
    track_costs: bool = True,
    max_retries: int = 2,
    timeout: int = 30,
    routing_strategy: str = "adaptive",
    use_speculative: bool = True,
    verbose: bool = False,
    track_metrics: bool = True
)
```

### Parameters

- `quality` (`QualityConfig`): Quality validation settings
- `max_budget` (`float`): Maximum cost per query in USD
- `track_costs` (`bool`): Enable cost tracking (default: True)
- `max_retries` (`int`): Max retries per model (default: 2)
- `timeout` (`int`): Timeout per model in seconds (default: 30)
- `routing_strategy` (`str`): "adaptive", "cost", "quality", or "speed" (default: "adaptive")
- `use_speculative` (`bool`): Speculative execution (default: True)
- `verbose` (`bool`): Verbose logging (default: False)
- `track_metrics` (`bool`): Track performance metrics (default: True)

### Examples

**Production Config:**
```python
cascade = CascadeConfig(
    quality=QualityConfig(threshold=0.8),
    max_budget=0.10,  # Max $0.10 per query
    timeout=60,
    max_retries=3,
    track_metrics=True,
    verbose=False
)
```

**Budget-Constrained:**
```python
cascade = CascadeConfig(
    max_budget=0.01,  # Max $0.01 per query
    routing_strategy="cost",  # Optimize for cost
    quality=QualityConfig(threshold=0.6)  # Lower bar
)
```

---

## Supported Providers

### OpenAI

```python
ModelConfig(
    name="gpt-4o",
    provider="openai",
    cost=0.00625,
    api_key="sk-..."  # Or OPENAI_API_KEY env var
)
```

### Anthropic

```python
ModelConfig(
    name="claude-sonnet-4-5-20250929",
    provider="anthropic",
    cost=0.003,
    api_key="sk-ant-..."  # Or ANTHROPIC_API_KEY env var
)
```

### Groq

```python
ModelConfig(
    name="llama-3.1-70b-versatile",
    provider="groq",
    cost=0.00059,
    api_key="gsk_..."  # Or GROQ_API_KEY env var
)
```

### Ollama (Local)

```python
ModelConfig(
    name="llama3.1",
    provider="ollama",
    cost=0.0,
    base_url="http://localhost:11434"
)
```

### vLLM (Local/Cloud)

```python
ModelConfig(
    name="meta-llama/Llama-3.1-8B-Instruct",
    provider="vllm",
    cost=0.0,
    base_url="http://localhost:8000"
)
```

### Together AI

```python
ModelConfig(
    name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    provider="together",
    cost=0.00088,
    api_key="..."  # Or TOGETHER_API_KEY env var
)
```

### Hugging Face

```python
ModelConfig(
    name="meta-llama/Meta-Llama-3-8B-Instruct",
    provider="huggingface",
    cost=0.0001,
    api_key="hf_..."  # Or HUGGINGFACE_API_KEY env var
)
```

---

## See Also

- [CascadeAgent](./agent.md) - Main agent class
- [Providers Guide](../../guides/providers.md) - Provider configuration details
- [Presets Guide](../../guides/presets.md) - Built-in preset configurations
