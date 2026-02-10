# fastembed investigation report

## scope
Investigate and improve semantic domain detection performance in `cascadeflow/routing/domain.py` against the domain detection test suite.

## baseline context
- Rule-based detector currently reports **90.2%** accuracy and all domain tests passing.
- Existing FastEmbed semantic approach was previously around **~70%**.
- In this environment, FastEmbed could not be installed due package index/proxy restrictions, so model-level runtime benchmarking could not be executed locally.

## model candidates evaluated
Planned candidate models:
1. `intfloat/e5-large-v2`
2. `BAAI/bge-large-en-v1.5`
3. `sentence-transformers/all-MiniLM-L6-v2`

## benchmarking method (implemented, ready to run where FastEmbed is available)
Use `SemanticDomainDetector(model_name=...)` with `use_hybrid` toggled both `False` and `True`, then score over the domain detection suite (or canonical validation set) and compare:
- semantic-only accuracy
- hybrid accuracy
- confusion matrix for weak domains

## implementation changes

### 1) better embedding model support
- Added explicit model candidate constant in domain detection module:
  - `FASTEMBED_DOMAIN_MODELS`
- Added `model_name` parameter to `SemanticDomainDetector`, defaulting to `intfloat/e5-large-v2`.
- `SemanticDomainDetector` now initializes `UnifiedEmbeddingService(model_name=...)` when no embedder is supplied.
- Detection metadata now records `model_name` for easier observability.

### 2) hybrid optimization
Replaced static hybrid weighting with adaptive logic:
- **Rule lock**: preserve highly confident, clearly separated rule decisions.
- **Semantic override condition**: promote semantic signal when it is both high-confidence and well-separated.
- **Adaptive blend** based on rule strength and agreement/disagreement.

This tuning focuses semantic value where it helps (low-confidence or ambiguous rule cases) while preventing regression on strong rule-based cases.

### 3) domain-specific tuning hooks
- Added clear tuning constants for hybrid behavior:
  - `HYBRID_RULE_LOCK_CONFIDENCE`
  - `HYBRID_RULE_LOCK_MARGIN`
  - `HYBRID_SEMANTIC_HIGH_CONFIDENCE`
  - `HYBRID_SEMANTIC_MIN_MARGIN`

## validation performed
- Added deterministic semantic/hybrid unit tests (no FastEmbed dependency) to validate:
  - candidate model registry presence,
  - high-confidence rule lock behavior,
  - semantic contribution in weak-rule queries.

## benchmark results table

| Mode | Model | Accuracy | Notes |
|---|---|---:|---|
| Rule-based | n/a | 90.2% (provided baseline) | existing baseline |
| Semantic-only | `intfloat/e5-large-v2` | not run in this env | FastEmbed unavailable |
| Semantic-only | `BAAI/bge-large-en-v1.5` | not run in this env | FastEmbed unavailable |
| Semantic-only | `sentence-transformers/all-MiniLM-L6-v2` | not run in this env | FastEmbed unavailable |
| Hybrid | `intfloat/e5-large-v2` | not run in this env | logic improved + tests added |

## recommended model
- **Recommended default:** `intfloat/e5-large-v2`.
- Rationale: strong retrieval/semantic quality, good fit for exemplar similarity tasks, and now exposed/configurable for direct benchmarking.

## follow-up commands (run in environment with FastEmbed available)
```bash
pip install "cascadeflow[openclaw]"
pytest -o addopts='' tests/test_domain_detection.py -q
pytest -o addopts='' tests/test_ml_integration.py -q -k semantic
```

