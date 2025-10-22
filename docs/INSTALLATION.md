# CascadeFlow Installation Guide

## 📦 Files

```
requirements.txt       → Core dependencies only (2 packages)
requirements-dev.txt   → Development + all providers + testing tools
```

## 🎯 Installation Options

### Production Users

```bash
# Minimal install (just core)
pip install cascadeflow

# With specific provider
pip install cascadeflow[openai]
pip install cascadeflow[anthropic]

# With common providers (OpenAI + Anthropic + Groq)
pip install cascadeflow[providers]

# With everything
pip install cascadeflow[all]
```

### Developers/Contributors

```bash
# Method 1: Using requirements-dev.txt
pip install -r requirements-dev.txt

# Method 2: Using pyproject.toml extras (recommended)
pip install -e ".[dev]"
```

## 📊 What's Included

### requirements.txt (Core Only)
```
pydantic>=2.0.0      # Data validation
httpx>=0.25.0        # HTTP client
```

**That's it!** Just 2 core dependencies. Providers are optional extras.

### requirements-dev.txt (Everything)
```
Core dependencies       ✅
All provider SDKs       ✅ (openai, anthropic, groq, huggingface, together, vllm)
Testing tools           ✅ (pytest, pytest-asyncio, pytest-cov, pytest-mock)
Code quality tools      ✅ (black, ruff, mypy, isort, pre-commit)
Development utilities   ✅ (rich for terminal output)
```

## 🆓 Free/Local Providers

### Ollama (Recommended for Development)
```bash
# No Python package needed!

# 1. Install Ollama from https://ollama.ai
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a model
ollama pull llama3.2:1b

# 3. Use with CascadeFlow
pip install cascadeflow  # Core only, no extras needed!
```

**Cost: $0/month** 💰

### vLLM
```bash
# Option 1: HTTP server (no Python package)
# Run vLLM server, connect via HTTP

# Option 2: Python package
pip install cascadeflow[vllm]
```

## 🔑 Provider Setup

### API Keys (.env file)
```bash
# Only add keys for providers you want to use

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Groq (free tier available!)
GROQ_API_KEY=gsk_...

# HuggingFace
HF_TOKEN=hf_...

# Together.ai
TOGETHER_API_KEY=...

# Ollama - no API key needed! (local)
# vLLM - no API key needed! (local)
```

## 🚀 Quick Start

### For Production
```bash
# Install with common providers
pip install cascadeflow[providers]

# Set API keys in .env
echo "OPENAI_API_KEY=sk-..." >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# Start using
python your_app.py
```

### For Development
```bash
# Clone repo
git clone https://github.com/lemony-ai/cascadeflow.git
cd cascadeflow

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest
```

## 🧪 Testing Without API Keys

Use Ollama for free local testing:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a small model
ollama pull llama3.2:1b

# Install just core CascadeFlow
pip install cascadeflow

# Test
python examples/ollama_example.py
```

## 📋 Dependencies Summary

| Package | Used By | Required? | Install Via |
|---------|---------|-----------|-------------|
| pydantic | Core validation | ✅ Always | requirements.txt |
| httpx | Core HTTP client | ✅ Always | requirements.txt |
| openai | OpenAIProvider | ❌ Optional | `[openai]` or `[providers]` or `[all]` |
| anthropic | AnthropicProvider | ❌ Optional | `[anthropic]` or `[providers]` or `[all]` |
| groq | GroqProvider | ❌ Optional | `[groq]` or `[providers]` or `[all]` |
| huggingface-hub | HuggingFaceProvider | ❌ Optional | `[huggingface]` or `[all]` |
| together | TogetherProvider | ❌ Optional | `[together]` or `[all]` |
| vllm | VLLMProvider | ❌ Optional | `[vllm]` or `[all]` |
| rich | Dev/Debug | ❌ Dev only | requirements-dev.txt |
| pytest | Testing | ❌ Dev only | requirements-dev.txt |
| black | Formatting | ❌ Dev only | requirements-dev.txt |
| ruff | Linting | ❌ Dev only | requirements-dev.txt |
| mypy | Type checking | ❌ Dev only | requirements-dev.txt |

## 💡 Best Practices

### For Production
1. **Start minimal**: `pip install cascadeflow`
2. **Add providers as needed**: `pip install cascadeflow[openai]`
3. **Use Ollama** for free local inference

### For Development
1. **Always use virtual environment**
2. **Install in editable mode**: `pip install -e ".[dev]"`
3. **Run tests** before committing: `pytest`
4. **Format code**: `black . && isort .`
5. **Check types**: `mypy cascadeflow/`

### For Testing
1. **Use Ollama** for free testing (no API costs!)
2. **Mock API calls** when testing without keys
3. **Use pytest fixtures** for provider initialization

## 🔧 Troubleshooting

### "No module named 'openai'"
```bash
# Install OpenAI extra
pip install cascadeflow[openai]
```

### "No module named 'anthropic'"
```bash
# Install Anthropic extra
pip install cascadeflow[anthropic]
```

### "Connection refused" with Ollama
```bash
# Make sure Ollama is running
ollama serve

# Check if running
curl http://localhost:11434/api/tags
```

### Version conflicts
```bash
# Create fresh virtual environment
python -m venv .venv
source .venv/bin/activate
pip install cascadeflow[providers]
```

### IDE shows missing dependencies
```bash
# Sync your IDE with virtual environment
# In PyCharm/IntelliJ: File → Project Structure → SDK
# Select .venv/bin/python

# Or reinstall
pip install -r requirements-dev.txt
```

## 🎯 Installation Examples by Use Case

### "I want to try CascadeFlow with OpenAI"
```bash
pip install cascadeflow[openai]
```

### "I want OpenAI + Anthropic"
```bash
pip install cascadeflow[openai,anthropic]
# or
pip install cascadeflow[providers]
```

### "I want everything"
```bash
pip install cascadeflow[all]
```

### "I want free local models only"
```bash
pip install cascadeflow
# Then install Ollama from https://ollama.ai
```

### "I'm contributing to CascadeFlow"
```bash
git clone https://github.com/lemony-ai/cascadeflow.git
cd cascadeflow
pip install -e ".[dev]"
pre-commit install
pytest
```

## ✅ Verification

Test your installation:

```bash
# Core
python -c "import cascadeflow; print('✅ Core OK')"

# OpenAI (if installed)
python -c "import openai; print('✅ OpenAI OK')"

# Anthropic (if installed)
python -c "import anthropic; print('✅ Anthropic OK')"

# Full test
python -c "
from cascadeflow import CascadeAgent, ModelConfig
print('✅ All imports working!')
"
```

## 📊 Provider Comparison

| Provider | Cost | Speed | Quality | Setup | API Key |
|----------|------|-------|---------|-------|---------|
| OpenAI | $$$ | Medium | High | Easy | Yes |
| Anthropic | $$$ | Medium | High | Easy | Yes |
| Groq | $ | Fast | Medium | Easy | Yes |
| Ollama | Free | Fast | Medium | Medium | No |
| vLLM | Free | Very Fast | Medium | Hard | No |

## 🔗 Links

- **pyproject.toml**: See all available extras
- **Documentation**: https://docs.lemony.ai/cascadeflow
- **Repository**: https://github.com/lemony-ai/cascadeflow
- **Issues**: https://github.com/lemony-ai/cascadeflow/issues

## 📝 Notes

- **tiktoken removed**: Not used in current implementation
- **Semantic routing**: Coming in future release
- **Ollama**: No Python package needed - uses HTTP directly
- **Core is minimal**: Only 2 dependencies for maximum flexibility