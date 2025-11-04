# ML Semantic Detection Snippets for README

This directory contains optional code snippets showing how to enable ML-based semantic domain detection in CascadeFlow.

## Files

### 1. `python_ml_quickstart.md`
**Location to add:** After line 155 in main README.md (after the basic Python quickstart example)

**What it shows:**
- How to install `cascadeflow[ml]` for semantic detection
- That the same code works without any changes
- How to check which detection method was used
- Benefits: 84-87% confidence, automatic fallback

**Key message:** "Just install and go - zero code changes needed"

---

### 2. `typescript_ml_quickstart.md`
**Location to add:** After line 182 in main README.md (after the basic TypeScript quickstart example)

**What it shows:**
- Note that ML detection is Python-only currently
- Preview of future TypeScript API (when available)
- Reassurance that rule-based detection works great
- Same benefits as Python version

**Key message:** "Coming soon for TypeScript - Python has it now"

---

## Design Decisions

### Collapsible Sections
Both snippets use `<details>` tags so they:
- Don't clutter the main quickstart
- Are discoverable for users who want better accuracy
- Can be easily expanded by interested users

### Minimal Changes Required
The snippets emphasize:
- **Optional** - not required for basic usage
- **Automatic** - no code changes needed after install
- **Fallback** - gracefully degrades if unavailable
- **Drop-in** - uses existing cascade setup

### Clear Benefits
Each snippet highlights:
- 🎯 84-87% confidence on complex domains
- 🔄 Automatic fallback to rule-based
- 📦 Zero code changes
- 🚀 Works with existing setup

---

## Usage Instructions

### For Python Section (README.md line 155):
1. Open README.md
2. Find line 155 (end of Python quickstart code block)
3. Insert the content from `python_ml_quickstart.md`
4. Verify formatting renders correctly

### For TypeScript Section (README.md line 182):
1. Open README.md
2. Find line 182 (end of TypeScript quickstart code block)
3. Insert the content from `typescript_ml_quickstart.md`
4. Verify formatting renders correctly

---

## Technical Background

### How ML Detection Works (Python)
- Uses FastEmbed with BGE-small-en-v1.5 embeddings
- Computes semantic similarity between query and domain exemplars
- Implementation: `cascadeflow/routing/domain.py:797-806`
- Enhanced exemplars: 8 diverse examples per domain (MATH, STRUCTURED, etc.)

### Automatic Fallback
```python
# In cascadeflow/routing/domain.py
if self._embedding_service.is_available:
    # Use ML semantic detection
    result = self._compute_semantic_similarity(query)
else:
    # Gracefully fall back to rule-based
    result = self._compute_rule_based_detection(query)
```

### Installation Details
```bash
# Python - installs FastEmbed
pip install cascadeflow[ml]

# TypeScript - not yet available
# npm install @cascadeflow/ml  # Coming soon
```

---

## Preview

### Python Snippet Preview
```python
# Install ML support
pip install cascadeflow[ml]

# Same code as before - no changes!
agent = CascadeAgent(models=[...])
result = await agent.run("Calculate eigenvalues")

# Check if ML was used
print(result.metadata.get('detection_method'))  # 'semantic' or 'rule-based'
```

### TypeScript Snippet Preview
```tsx
// Currently Python-only
// Rule-based detection works great for now!

// Future API (when available):
// npm install @cascadeflow/ml
const agent = new CascadeAgent({ models: [...] });
const result = await agent.run('Parse JSON schema');
console.log(result.metadata.detectionMethod);  // Will show method used
```
