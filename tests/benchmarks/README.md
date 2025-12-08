### Benchmark Suite

Professional benchmarks to validate CascadeFlow performance across real-world use cases.

#### Datasets

1. **HumanEval** - Code generation (164 programming problems)
2. **Bitext Customer Support** - Customer service Q&A (27,000+ examples)
3. **Banking77** - Banking intent classification (13,000+ examples)
4. **GSM8K** - Grade school math reasoning (8,500+ problems)

#### Metrics

Each benchmark measures:
- **Cost savings** vs. always-powerful-model baseline
- **Quality maintenance** (accuracy/pass rate)
- **Latency** improvements
- **Escalation rates** (drafter acceptance %)

#### Running Benchmarks

```bash
# Run a single benchmark
python -m benchmarks.datasets.humaneval

# Run all benchmarks
python -m benchmarks.run_all

# View results
ls benchmarks/results/
```

#### Output

- **JSON**: Detailed results for analysis
- **CSV**: Tabular data for Excel/graphs
- **Markdown**: Human-readable reports with ROI calculations

#### Structure

```
benchmarks/
├── base.py          # Abstract benchmark class
├── metrics.py       # Cost/latency/quality calculations
├── reporter.py      # Report generation
├── humaneval.py     # Code generation benchmark
├── customer_support.py  # Customer service Q&A
├── banking77.py     # Banking intent classification
├── gsm8k.py         # Math reasoning
└── results/         # Output directory
```

All benchmarks extend the `Benchmark` base class.
