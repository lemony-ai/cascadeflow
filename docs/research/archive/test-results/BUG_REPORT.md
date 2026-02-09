# Bug Report

## 1) TypeScript alignment scorer lacks v12–v14 boosts

### Summary
Python alignment scoring applies v12 (long context QA), v13 (function call), and v14 (short-answer long context) boosts. The TypeScript port stops at v10, producing lower alignment scores and failing parity requirements.

### Reproduction Steps
1. Run:
   ```bash
   python tests/e2e/alignment_parity.py
   ```
2. Observe mismatches for `v12_long_context`, `v13_function_call`, and `v14_long_context_short_answer`.

### Expected
Scores should match within 0.05 tolerance between Python and TypeScript.

### Actual
TypeScript scores are lower by 0.30–0.67 for v12–v14 cases.

### Root Cause
`packages/core/src/alignment.ts` is based on Python v10 and does not include the v12–v14 format detection and boosts present in `cascadeflow/quality/alignment_scorer.py`.

### Suggested Fix
Port v11–v14 logic to TypeScript:
- Intent classification detection (v11)
- Long-context QA detection (v12)
- Function call detection (v13)
- Short-answer handling for long-context QA (v14)

---

## 2) Proxy server module missing

### Summary
Proxy E2E tests cannot run because `cascadeflow.proxy.server` module does not exist in the Python package.

### Reproduction Steps
1. Run:
   ```bash
   python tests/e2e/proxy_e2e.py
   ```
2. Script reports `cascadeflow.proxy.server module not found`.

### Expected
Proxy server starts and accepts OpenAI/Anthropic formatted requests.

### Actual
Module not found; proxy cannot start.

### Root Cause
No `cascadeflow.proxy` package/module exists in the repository, despite test requirements referencing it.

### Suggested Fix
- Confirm intended proxy server module location.
- Add or expose `cascadeflow.proxy.server`, or update documentation and tests to point to the correct proxy entrypoint.

