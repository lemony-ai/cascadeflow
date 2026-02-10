#!/usr/bin/env bash
set -euo pipefail

# Extended E2E validation session (real APIs).
#
# Usage:
#   set -a && source .env && set +a
#   ./scripts/extended-e2e-session.sh smoke
#
# Profiles: smoke | standard | overnight | full

PROFILE="${1:-smoke}"
TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="benchmark_results/sessions/${TS}_${PROFILE}"

mkdir -p "${OUTDIR}"

{
  echo "timestamp=${TS}"
  echo "profile=${PROFILE}"
  echo "git_sha=$(git rev-parse HEAD)"
  echo "git_branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "node=$(node -v 2>/dev/null || true)"
  echo "pnpm=$(pnpm -v 2>/dev/null || true)"
  echo "python=$(python3 -V 2>/dev/null || true)"
} >"${OUTDIR}/meta.txt"

echo "Output: ${OUTDIR}"

echo
echo "== TS + Python Unit/Integration Tests =="
pnpm test 2>&1 | tee "${OUTDIR}/pnpm_test.log"
python3 -m pytest 2>&1 | tee "${OUTDIR}/pytest.log"

echo
echo "== Vercel AI Handler E2E (TS) =="
pnpm -C packages/core exec vitest run \
  src/vercel-ai/__tests__/e2e.test.ts \
  src/__tests__/vercel-ai-chat-handler.e2e.test.ts 2>&1 | tee "${OUTDIR}/vercel_ai_e2e_vitest.log"

echo
echo "== TS Real API Smoke (optional) =="
pnpm -C packages/core run real-api:smoke 2>&1 | tee "${OUTDIR}/ts_real_api_smoke.log" || true

echo
echo "== Python Benchmarks (triad) =="
python3 tests/benchmarks/run_benchmarks.py \
  $([[ "${PROFILE}" == "smoke" ]] && echo "--quick" || true) \
  --output "${OUTDIR}/triad.json" 2>&1 | tee "${OUTDIR}/triad.log" || true

echo
echo "== Python Benchmarks (broad suite) =="
python3 -m tests.benchmarks.run_all \
  --profile "${PROFILE}" \
  --output-dir "${OUTDIR}/run_all" 2>&1 | tee "${OUTDIR}/run_all.log"

echo
echo "Completed. Results in: ${OUTDIR}"

