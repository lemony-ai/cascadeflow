<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/lemony-ai/CascadeFlow/feature/cost-control-quality-v2/.github/assets/Lemony_logo_bright.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/lemony-ai/CascadeFlow/feature/cost-control-quality-v2/.github/assets/Lemony_logo_dark.svg">
  <img alt="Lemony Logo" src="https://raw.githubusercontent.com/lemony-ai/CascadeFlow/feature/cost-control-quality-v2/.github/assets/Lemony_logo_dark.svg" width="300">
</picture>

**Open, developer-focused AI infrastructure**

[![Website](https://img.shields.io/badge/Website-lemony.ai-blue)](https://lemony.ai)
[![X Follow](https://img.shields.io/twitter/follow/SaschaBuehrle?style=social)](https://x.com/SaschaBuehrle)
[![GitHub Stars](https://img.shields.io/github/stars/lemony-ai/cascadeflow?style=social)](https://github.com/lemony-ai/cascadeflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[**Documentation**](https://github.com/lemony-ai/cascadeflow#readme) • [**Follow @SaschaBuehrle on X**](https://x.com/SaschaBuehrle) • [**Community**](https://github.com/orgs/lemony-ai/discussions)

</div>

---

## About Lemony

Lemony builds **open, developer-focused AI infrastructure tools** that make machine learning more efficient, transparent, and cost-effective.

Our mission is to help developers harness powerful AI while keeping costs predictable and accessible, while preparing for a future where hundreds of domain-specific small language models need to work safely together.

---

## 🚀 Featured Project

### [Cascadeflow](https://github.com/lemony-ai/cascadeflow)

**Smart AI model cascading for cost optimization.**

Cascadeflow is an intelligent AI model cascading library that dynamically selects the optimal model for each query or tool call through speculative execution. It's based on the research that 40-70% of queries don't require slow, expensive flagship models, and domain-specific smaller models often outperform large general-purpose models on specialized tasks. For the remaining queries that need advanced reasoning, Cascadeflow automatically escalates to flagship models if needed.

**Cut Costs 30-65% in 3 Lines of Code. One cascade. Hundreds of specialists.**

```python
pip install cascadeflow
```

```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
])

result = await agent.run("What is TypeScript?")
# Automatically routes to optimal model, saves 40-85% on costs
```

**Key Features:**
- ⚡ **Sub-2ms overhead** - Negligible performance impact
- 💰 **40-85% cost savings** - Research-backed, production-proven
- 🔄 **Mix any providers** - OpenAI, Anthropic, Groq, Ollama, vLLM, Together
- 🧠 **Domain understanding** - Auto-detects code, medical, legal, math queries
- 🏭 **Production ready** - Streaming, tool calling, batch processing

[**Get Started →**](https://github.com/lemony-ai/cascadeflow) | [**Read Docs →**](https://docs.lemony.ai)

---

## 💡 Philosophy

### Open Source First
All core infrastructure is open source. We believe the future of AI tooling is transparent, auditable, and community-driven.

### Developer Experience
Zero vendor lock-in. Works with your existing models, providers, and architecture. Deploy anywhere.

### Production Ready
Built for real workloads. Sub-2ms overhead, fault-tolerant, with comprehensive error handling.

### Cost Transparency
Every query tracked. Built-in analytics. Programmable budget limits. No surprise bills.

---

## 📊 By The Numbers

- **40-85%** average cost reduction in production
- **<2ms** framework overhead
- **7+** supported AI providers (OpenAI, Anthropic, Groq, Ollama, vLLM, Together, HuggingFace)
- **100+** additional providers via LiteLLM integration
- **60-70%** of queries handled by fast, efficient models

---

## 🌍 Community

We're building Lemony in public. Join our community:

- **[GitHub Discussions](https://github.com/orgs/lemony-ai/discussions)** - Ask questions, share ideas
- **[X/Twitter](https://x.com/SaschaBuehrle)** - Latest updates and announcements
- **[Issues](https://github.com/lemony-ai/cascadeflow/issues)** - Bug reports and feature requests
- **[Contributing](https://github.com/lemony-ai/cascadeflow/blob/main/CONTRIBUTING.md)** - Help build the future of AI infrastructure

---

## 🤝 Contributing

We welcome contributions! Whether it's:

- 🐛 Bug reports and fixes
- ✨ Feature requests and implementations
- 📝 Documentation improvements
- 💡 New ideas and feedback

See our [Contributing Guide](https://github.com/lemony-ai/cascadeflow/blob/main/CONTRIBUTING.md) to get started.

---

## 📬 Contact

- **Website**: [lemony.ai](https://lemony.ai)
- **Email**: hello@lemony.ai
- **X/Twitter**: [@SaschaBuehrle](https://x.com/SaschaBuehrle)
- **GitHub**: [@lemony-ai](https://github.com/lemony-ai)

---

## 📄 License

Our core projects are MIT licensed. See the [Cascadeflow LICENSE](https://github.com/lemony-ai/cascadeflow/blob/main/LICENSE) for details.

---

<div align="center">

**Built with ❤️ by developers, for developers**

[**Documentation**](https://github.com/lemony-ai/cascadeflow#readme) • [**Follow @SaschaBuehrle on X**](https://x.com/SaschaBuehrle) • [**Community**](https://github.com/orgs/lemony-ai/discussions)

[![GitHub Stars](https://img.shields.io/github/stars/lemony-ai/cascadeflow?style=social)](https://github.com/lemony-ai/cascadeflow)

</div>
