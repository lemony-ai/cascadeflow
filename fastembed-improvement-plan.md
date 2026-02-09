# FastEmbed Implementation Improvement Plan

## Current State Analysis

Based on deep evaluation:
- **FastEmbed 30-44% faster** on long queries (excellent)
- **Rule-based 67% domain accuracy** vs FastEmbed 58%
- **FastEmbed misses**: conversation, finance (as "general")
- **Both miss**: factual, reasoning domains

## Root Causes

1. **DOMAIN_EXEMPLARS incomplete** - finance, conversation, factual, reasoning lack good exemplars
2. **Hybrid mode not enabled by default** - could combine best of both
3. **Confidence threshold too high** (0.6) - some domains need lower thresholds
4. **No complexity-aware domain detection** - complexity should influence domain routing

## Improvement Opportunities

### 1. Enhanced Domain Exemplars (HIGH IMPACT)

Add more exemplars for weak domains:

```python
DOMAIN_EXEMPLARS = {
    # ... existing ...
    
    Domain.FINANCIAL: [
        "Explain compound interest",  # ADD
        "Calculate ROI on investment",  # ADD
        "What are the tax implications",  # ADD
        "Portfolio diversification strategy",  # ADD
        "Explain P/E ratio",  # ADD
    ],
    
    Domain.CONVERSATION: [
        "How are you today?",  # ADD
        "Nice to meet you",  # ADD
        "Let's chat about",  # ADD
        "What do you think?",  # ADD
        "Tell me more",  # ADD
    ],
    
    Domain.FACTUAL: [
        "What is the capital of France?",  # ADD
        "When did World War II end?",  # ADD
        "Who invented the telephone?",  # ADD
        "What is the population of",  # ADD
        "Is it true that",  # ADD
    ],
    
    Domain.REASONING: [  # NEW DOMAIN OR MAP TO GENERAL
        "If A then B, what about C?",
        "Compare and contrast",
        "What are the implications of",
        "Logical deduction",
        "Syllogism",
    ],
}
```

### 2. Smart Hybrid Mode (MEDIUM IMPACT)

Enable hybrid by default with smart combination:

```python
class SmartDomainDetector:
    """
    Combines rule-based and semantic detection optimally.
    
    Strategy:
    - Rule-based first (fast, good for clear keywords)
    - If rule confidence < 0.7, use semantic for second opinion
    - If they agree, boost confidence
    - If they disagree, prefer semantic for nuanced queries
    """
    
    def detect(self, query: str) -> tuple[Domain, float]:
        # Fast rule-based first
        rule_domain, rule_conf = self.rule_detector.detect(query)
        
        # If high confidence, trust rule-based (saves latency)
        if rule_conf >= 0.85:
            return rule_domain, rule_conf
        
        # For uncertain cases, consult semantic
        if self.semantic_available:
            sem_domain, sem_conf = self.semantic_detector.detect(query)
            
            # Agreement boosts confidence
            if rule_domain == sem_domain:
                return rule_domain, min(0.95, rule_conf + 0.15)
            
            # Disagreement - prefer higher confidence
            if sem_conf > rule_conf:
                return sem_domain, sem_conf
        
        return rule_domain, rule_conf
```

### 3. Domain-Specific Confidence Thresholds (MEDIUM IMPACT)

```python
DOMAIN_THRESHOLDS = {
    Domain.CODE: 0.65,       # Code is distinctive
    Domain.MEDICAL: 0.70,    # Need high confidence for medical
    Domain.LEGAL: 0.70,      # Need high confidence for legal
    Domain.CONVERSATION: 0.50,  # Lower threshold (often missed)
    Domain.FINANCIAL: 0.55,  # Lower threshold (often missed)
    Domain.FACTUAL: 0.50,    # Lower threshold (often missed)
    Domain.GENERAL: 0.40,    # Fallback domain
}
```

### 4. Add FastEmbed to Complexity Detection (HIGH IMPACT)

Currently complexity uses rule-based only. Add semantic layer:

```python
# In complexity.py
class SemanticComplexityBooster:
    """
    Use embeddings to detect complex query patterns.
    
    Embeddings for complexity exemplars:
    - "Prove X is true" -> expert
    - "Implement production-ready" -> hard
    - "What is X?" -> simple
    """
    
    COMPLEXITY_EXEMPLARS = {
        "expert": [
            "Prove mathematically that",
            "Derive from first principles",
            "Design a distributed system",
            "Implement a lock-free algorithm",
        ],
        "hard": [
            "Explain the implications of",
            "Implement with error handling",
            "Compare trade-offs between",
        ],
        "moderate": [
            "Explain how X works",
            "Compare X and Y",
            "What are the advantages of",
        ],
        "simple": [
            "What is X?",
            "Define X",
            "List examples of",
        ],
        "trivial": [
            "Hi",
            "Hello",
            "What is 2+2?",
        ],
    }
```

### 5. Quality Validation Enhancement (LOW IMPACT)

Use FastEmbed for query-response alignment:

```python
class SemanticAlignmentChecker:
    """
    Check if response semantically aligns with query.
    
    Uses cosine similarity between query and response embeddings.
    Low similarity = potential off-topic response.
    """
    
    def check_alignment(self, query: str, response: str) -> float:
        q_emb = self.embedder.embed(query)
        r_emb = self.embedder.embed(response)
        return cosine_similarity(q_emb, r_emb)
```

## Implementation Priority

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| P0 | Add domain exemplars | HIGH | LOW |
| P0 | Enable hybrid mode by default | HIGH | LOW |
| P1 | Domain-specific thresholds | MEDIUM | LOW |
| P1 | SemanticComplexityBooster | HIGH | MEDIUM |
| P2 | SemanticAlignmentChecker | LOW | MEDIUM |

## Files to Modify

1. `cascadeflow/routing/domain.py`
   - Add DOMAIN_EXEMPLARS for finance, conversation, factual
   - Update SemanticDomainDetector with domain-specific thresholds
   - Enable hybrid mode by default

2. `cascadeflow/quality/complexity.py`
   - Add SemanticComplexityBooster class
   - Integrate with existing detect() method

3. `cascadeflow/quality/quality.py`
   - Add SemanticAlignmentChecker (optional)

4. `tests/test_domain_detection.py`
   - Add tests for new exemplars
   - Add tests for hybrid mode

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Finance domain detection | 0% | 80%+ |
| Conversation detection | 50% (rule only) | 90%+ |
| Factual detection | 0% | 70%+ |
| Reasoning detection | 0% | 70%+ |
| Overall domain accuracy | 58-67% | 85%+ |
