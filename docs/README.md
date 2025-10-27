# CascadeFlow Documentation

Welcome to CascadeFlow documentation! 🌊

## 📖 Quick Links

- [Installation Guide](INSTALLATION.md)
- [Quick Start Guide](guides/quickstart.md)
- [GPT-5 Setup Guide](GPT-5-SETUP.md)
- [Model Availability](MODEL-AVAILABILITY.md)
- [TypeScript vs Python Comparison](TYPESCRIPT_PYTHON_COMPARISON.md)

## 🚀 Getting Started

### Core Concepts
- [Quickstart](guides/quickstart.md) - Get started with CascadeFlow in 5 minutes
- [Providers](guides/providers.md) - Configure and use different AI providers (OpenAI, Anthropic, Groq, Ollama, etc.)
- [Presets](guides/presets.md) - Use built-in presets for common use cases

### Core Features
- [Streaming](guides/streaming.md) - Stream responses from cascade agents
- [Tools](guides/tools.md) - Function calling and tool usage with cascades
- [Cost Tracking](guides/cost_tracking.md) - Track and analyze API costs across queries

## 🏭 Production & Advanced

### Production Deployment
- [Production Guide](guides/production.md) - Best practices for production deployments
- [Performance Guide](guides/performance.md) - Optimize cascade performance and latency
- [FastAPI Integration](guides/fastapi.md) - Integrate CascadeFlow with FastAPI applications

### Advanced Topics
- [Custom Cascades](guides/custom_cascade.md) - Build custom cascade strategies
- [Custom Validation](guides/custom_validation.md) - Implement custom quality validators
- [Edge Device Deployment](guides/edge_device.md) - Deploy cascades on edge devices (Jetson, etc.)
- [Browser/Edge Runtime](guides/browser_cascading.md) - Run cascades in browser or edge environments

### Integrations
- [n8n Integration](guides/n8n_integration.md) - Use CascadeFlow in n8n workflows

## 📚 Examples

See the [examples/](../examples/) directory for comprehensive working code samples:

**Python Examples:**
- Basic usage, preset usage, multi-provider
- Tool execution, streaming, cost tracking
- Production patterns, FastAPI integration
- Edge device deployment, vLLM integration
- Custom cascades and validation

**TypeScript Examples:**
- Basic usage, tool calling, multi-provider
- Streaming responses
- Production patterns
- Browser/Vercel Edge deployment

## 🤝 Need Help?

- 📖 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions) - Q&A and community support
- 🐛 [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues) - Bug reports and feature requests
- 📧 [Email Support](mailto:hello@lemony.ai) - Direct support

## 📦 API Reference

Comprehensive API documentation for all classes and methods:

- **[API Overview](./api/README.md)** - Complete API reference for Python and TypeScript
- **Python API**
  - [CascadeAgent](./api/python/agent.md) - Main agent class
  - [ModelConfig](./api/python/config.md) - Model and cascade configuration
  - [CascadeResult](./api/python/result.md) - Result object with 30+ diagnostic fields
- **TypeScript API** (coming soon)
  - CascadeAgent, ModelConfig, CascadeResult interfaces

See also: Comprehensive examples in [/examples](../examples/) directory

## 🏗️ Architecture & Contributing

For contributors and advanced users:

- **[Architecture Guide](../.analysis/STRUCTURE.md)** - Detailed architecture, data flow, and code organization
- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute to CascadeFlow

The architecture guide covers:
- Directory structure (monorepo layout)
- Core components and design patterns
- Data flow and execution paths
- Adding new providers, quality checks, and routing strategies
- Testing strategy and development workflow
