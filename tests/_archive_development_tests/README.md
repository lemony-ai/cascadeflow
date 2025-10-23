# Archived Development Tests

This directory contains test files that were created during development but are not part of the production test suite.

## Why These Were Archived

These tests were moved here during the 0.1.0 release preparation to:
1. Clean up the test directory for better organization
2. Remove debug/diagnostic scripts
3. Remove one-time validation tests
4. Keep the main test suite focused on core functionality

## Archived Files

### Debug & Diagnostic Tests
- `debug_together_api.py` - API debugging for Together AI
- `test_confidence_debug.py` - Confidence scoring debugging
- `test_together_logprobs_debug.py` - Logprobs debugging
- `diagnose_telemetry.py` - Telemetry diagnostics
- `test_diagnostic_integration.py` - Integration diagnostics
- `test_quick_diagnostic.py` - Quick diagnostic checks
- `test_api_provider_diagnostics.py` - Provider API diagnostics

### Analysis & Performance Tests
- `test_cascade_insights.py` - Cascade behavior analysis
- `test_cascade_performance_analysis.py` - Performance analysis
- `test_comprehensive_autotuning.py` - Autotuning experiments

### One-Time Validation Tests
- `cascadeflow_prelaunch_realworld_tests.py` - Pre-launch validation
- `test_phase0_provider_validation.py` - Phase 0 validation
- `test_system_validation.py` - System validation
- `verify_test_setup.py` - Test setup verification

### Interactive & Demo Tests
- `test_cascade_interactive.py` - Interactive testing
- `demo_streaming.py` - Streaming demo

### Investigation Scripts
- `provider_investigation.py` - Provider investigation
- `2.py` - Development script
- `run_week2_tests.py` - Week 2 specific tests

## Can I Delete These?

**Not recommended.** These tests contain valuable:
- Historical context about development decisions
- Debugging techniques that might be useful again
- Performance baselines
- Investigation methodologies

## When to Use These

You might want to reference these when:
- Debugging similar issues in the future
- Understanding why certain decisions were made
- Benchmarking new features against old baselines
- Investigating provider-specific behaviors

## Production Test Suite

The main test suite (in `tests/`) now contains:
- Core unit tests
- Integration tests
- Provider tests
- Quality system tests
- Routing tests
- Tool tests

---

**Archived:** October 23, 2025 during 0.1.0 release preparation
