### Benchmark Suite

Professional benchmarks to validate CascadeFlow performance across real-world use cases.

#### Datasets

1. **HumanEval** - Code generation (164 programming problems)
2. **Bitext Customer Support** - Customer service Q&A (27,000+ examples)
3. **Banking77** - Banking intent classification (13,000+ examples)
4. **GSM8K** - Grade school math reasoning (8,500+ problems)
5. **MT-Bench** - Multi-turn chat quality / routing behavior (sampled)
6. **TruthfulQA** - Factual correctness (sampled)
7. **Tool Calling** - Structured tool selection correctness (single + multi-turn)
8. **BFCL Agentic** - Agentic/multi-turn tool-calling patterns (dependencies, chaining)

#### Metrics

Each benchmark measures:
- **Cost savings** vs. always-powerful-model baseline
- **Quality maintenance** (accuracy/pass rate)
- **Latency** improvements
- **Escalation rates** (drafter acceptance %)

#### Running Benchmarks

```bash
# Load API keys (repo root .env)
set -a && source .env && set +a

# Run quick triad suite (GSM8K + MMLU + MT-Bench)
python3 tests/benchmarks/run_benchmarks.py --quick --output benchmark_results/e2e_quick.json || true

# Run broad suite (HumanEval, GSM8K, MT-Bench, TruthfulQA, Banking77, tool calling, etc.)
python3 -m tests.benchmarks.run_all --profile smoke --output-dir benchmark_results/smoke
```

#### Output

- **JSON**: Detailed results for analysis
- **CSV**: Tabular data for Excel/graphs
- **Markdown**: Human-readable reports with ROI calculations

#### Structure

```
tests/benchmarks/
├── base.py              # Benchmark base class + summary metrics
├── run_benchmarks.py    # GSM8K + MMLU + MT-Bench runner (targets)
├── run_all.py           # Broad suite runner (reports to benchmark_results/)
├── humaneval/           # HumanEval benchmark implementation
├── gsm8k/               # GSM8K benchmark implementation
├── mmlu/                # MMLU benchmark implementation
├── mtbench/             # MT-Bench benchmark implementation
├── truthfulqa.py        # TruthfulQA benchmark implementation
├── banking77_benchmark.py
├── customer_support.py
├── tool_calls.py
└── tool_calls_agentic.py
```

All benchmarks extend the `Benchmark` base class.
