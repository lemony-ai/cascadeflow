# Python ML Semantic Detection Snippet

**Add this after the basic Python quickstart code block (after line 155 in README.md)**

---

```markdown
<details>
<summary><b>💡 Optional: Enable ML-based Domain Detection for Higher Accuracy</b></summary>

Install the optional ML package for improved domain detection:

```python
pip install cascadeflow[ml]  # Adds semantic similarity detection
```

That's it! CascadeFlow automatically uses ML when available:

```python
from cascadeflow import CascadeAgent, ModelConfig

# Same setup as before - no code changes needed
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-5", provider="openai", cost=0.00125),
])

# ML semantic detection is now automatically enabled
result = await agent.run("Calculate the eigenvalues of matrix [[1,2],[3,4]]")

# Check detection method used
print(f"Domain: {result.metadata.get('domain_detected')}")
print(f"Method: {result.metadata.get('detection_method')}")  # Shows 'semantic' or 'rule-based'
print(f"Confidence: {result.metadata.get('domain_confidence', 0):.1%}")
```

**What you get:**
- 🎯 84-87% confidence on complex domains (MATH, CODE, DATA, STRUCTURED)
- 🔄 Automatic fallback to rule-based if ML unavailable
- 📦 Zero code changes - just install and go
- 🚀 Works with your existing cascade setup

</details>
```
