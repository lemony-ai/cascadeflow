# TypeScript ML Semantic Detection Snippet

**Add this after the basic TypeScript quickstart code block (after line 182 in README.md)**

---

```markdown
<details>
<summary><b>💡 Optional: Enable ML-based Domain Detection for Higher Accuracy</b></summary>

> **Note:** ML semantic detection is currently available in Python only. TypeScript support is planned for a future release. Rule-based detection provides excellent accuracy out of the box.

For Python users, install the optional ML package:

```bash
pip install cascadeflow[ml]  # Python only - adds semantic similarity detection
```

**Future TypeScript Support (Planned):**

```tsx
// Will be available in a future release
npm install @cascadeflow/ml

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

// Same setup as before - no code changes needed
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
});

// ML semantic detection will be automatically enabled
const result = await agent.run('Parse this JSON and validate the schema');

// Check detection method used
console.log(`Domain: ${result.metadata.domainDetected}`);
console.log(`Method: ${result.metadata.detectionMethod}`);  // Will show 'semantic' or 'rule-based'
console.log(`Confidence: ${(result.metadata.domainConfidence * 100).toFixed(1)}%`);
```

**What you'll get (when available):**
- 🎯 84-87% confidence on complex domains (MATH, CODE, DATA, STRUCTURED)
- 🔄 Automatic fallback to rule-based if ML unavailable
- 📦 Zero code changes - just install and go
- 🚀 Works with your existing cascade setup

Currently, cascadeflow TypeScript uses highly accurate rule-based domain detection which works great for most use cases!

</details>
```
