# CascadeFlow Production Benchmark Report

**Date**: 2025-10-28 08:21:00

**Providers Tested**: groq

**Total Queries**: 111

---

## Provider Comparison

| Provider | Queries | Avg Latency (ms) | P95 Latency (ms) | Avg Cost | Total Cost | Avg Tokens |
|----------|---------|------------------|------------------|----------|------------|------------|
| groq | 111 | 3932 | 30439 | $0.000026 | $0.002847 | 340 |

## Query Complexity Analysis

| Category | Queries | Avg Latency | Avg Cost | Avg Tokens |
|----------|---------|-------------|----------|------------|
| Trivial | 30 | 2353ms | $0.000005 | 74 |
| Simple | 30 | 2257ms | $0.000016 | 212 |
| Complex | 15 | 5823ms | $0.000053 | 682 |
| Expert | 9 | 12454ms | $0.000080 | 1020 |

## Key Insights

- **Fastest Provider**: groq (3932ms avg)
- **Cheapest Provider**: groq ($0.000026 avg)
- **Highest Confidence**: groq (57.3% avg)

## Recommendations

Based on the benchmark results:

1. **For Speed**: Use Groq if available (typically 4-5x faster)
2. **For Cost**: Groq and Together AI offer best value
3. **For Quality**: OpenAI and Anthropic show highest confidence scores
4. **For Production**: Consider cascade routing to balance all three

