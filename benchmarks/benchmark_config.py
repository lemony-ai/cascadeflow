"""Benchmark Configuration for CascadeFlow Optimization.

This module provides configurable benchmark settings for optimizing
CascadeFlow to achieve target cost reductions while maintaining quality.

Targets (vs GPT-4o/GPT-5 only):
- MT-Bench: ≥85% cost reduction, ≥95% quality
- MMLU: ≥45% cost reduction, ≥95% quality
- GSM8K: ≥35% cost reduction, ≥95% quality
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BenchmarkMode(Enum):
    """Benchmark configuration modes."""

    BASELINE = "baseline"  # No semantic, no domain pipeline
    SEMANTIC_ONLY = "semantic_only"  # Semantic detection, no domain pipeline
    DOMAIN_ONLY = "domain_only"  # Domain pipeline, no semantic detection
    FULL = "full"  # Both semantic detection and domain pipeline enabled


@dataclass
class ModelTier:
    """Model tier configuration with cost/capability info."""

    name: str
    provider: str
    cost_per_1k: float  # Cost per 1K tokens
    strengths: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.strengths:
            self.strengths = []


# Pre-configured model tiers (2025 optimized)
# GPT-5 Family: Best performance, excellent reasoning (74.9% SWE-bench)
# Haiku 4.5: Extended thinking, great cost/quality ratio
# LiteLLM handles pricing automatically
DRAFTER_MODELS = {
    "gpt-5-mini": ModelTier(
        name="gpt-5-mini",
        provider="openai",
        cost_per_1k=0.00025,  # $0.25/M input, $2/M output
        strengths=["general", "math", "code", "reasoning", "cost-effective"],
    ),
    "gpt-4o-mini": ModelTier(
        name="gpt-4o-mini",
        provider="openai",
        cost_per_1k=0.00015,  # $0.15/M input, $0.60/M output
        strengths=["general", "fast", "cost-effective"],
    ),
    "claude-haiku-4-5": ModelTier(
        name="claude-haiku-4-5-20251001",
        provider="anthropic",
        cost_per_1k=0.001,  # $1/M input, $5/M output
        strengths=["reasoning", "code", "creative", "extended-thinking"],
    ),
    "claude-3-5-haiku": ModelTier(
        name="claude-3-5-haiku-20241022",
        provider="anthropic",
        cost_per_1k=0.0008,  # $0.80/M input, $4/M output
        strengths=["fast", "reasoning", "cost-effective"],
    ),
}

VERIFIER_MODELS = {
    "gpt-5": ModelTier(
        name="gpt-5",
        provider="openai",
        cost_per_1k=0.00125,  # $1.25/M input, $10/M output
        strengths=["reasoning", "math", "code", "quality"],
    ),
    "gpt-4o": ModelTier(
        name="gpt-4o",
        provider="openai",
        cost_per_1k=0.0025,  # $2.50/M input, $10/M output
        strengths=["general", "quality", "vision"],
    ),
    "claude-sonnet-4-5": ModelTier(
        name="claude-sonnet-4-5-20250929",
        provider="anthropic",
        cost_per_1k=0.003,  # $3/M input, $15/M output
        strengths=["reasoning", "code", "quality"],
    ),
    "claude-opus-4-5": ModelTier(
        name="claude-opus-4-5-20251101",
        provider="anthropic",
        cost_per_1k=0.015,  # $15/M input, $75/M output
        strengths=["reasoning", "code-review", "quality"],
    ),
}


@dataclass
class DomainBenchmarkConfig:
    """Domain-specific benchmark configuration."""

    drafter: str
    verifier: str
    quality_threshold: float
    temperature: float = 0.7


# Optimized domain configurations for benchmarks (2025 models)
# GPT-5 Mini: Excellent math/code drafter ($0.25/M input)
# GPT-5: Best verifier, 74.9% SWE-bench ($1.25/M input)
# Haiku 4.5: Extended thinking, great for creative ($1/M input)
DOMAIN_CONFIGS = {
    # High accuracy domains - GPT-5 family for math/code
    "code": DomainBenchmarkConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - excellent code
        verifier="gpt-5",  # GPT-5 - best reasoning
        quality_threshold=0.85,
        temperature=0.1,
    ),
    "math": DomainBenchmarkConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - excellent math
        verifier="gpt-5",  # GPT-5 - best math reasoning
        quality_threshold=0.85,
        temperature=0.1,
    ),
    "reasoning": DomainBenchmarkConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - strong reasoning
        verifier="gpt-5",
        quality_threshold=0.80,
        temperature=0.3,
    ),
    "stem": DomainBenchmarkConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good for STEM
        verifier="gpt-5",
        quality_threshold=0.82,
        temperature=0.3,
    ),
    # Medium accuracy domains - balanced thresholds
    "extraction": DomainBenchmarkConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good structured output
        verifier="gpt-5",
        quality_threshold=0.75,
        temperature=0.2,
    ),
    "humanities": DomainBenchmarkConfig(
        drafter="claude-haiku-4-5-20251001",  # Haiku 4.5 - extended thinking
        verifier="claude-sonnet-4-5-20250929",  # Sonnet 4.5
        quality_threshold=0.72,
        temperature=0.5,
    ),
    "social_sciences": DomainBenchmarkConfig(
        drafter="claude-haiku-4-5-20251001",  # Haiku 4.5 - extended thinking
        verifier="claude-sonnet-4-5-20250929",
        quality_threshold=0.72,
        temperature=0.5,
    ),
    # Creative domains - Haiku 4.5 for creative tasks
    "writing": DomainBenchmarkConfig(
        drafter="claude-haiku-4-5-20251001",  # Haiku 4.5 - excellent creative
        verifier="claude-sonnet-4-5-20250929",  # Sonnet 4.5
        quality_threshold=0.65,
        temperature=0.7,
    ),
    "roleplay": DomainBenchmarkConfig(
        drafter="claude-haiku-4-5-20251001",  # Haiku 4.5 - good at roleplay
        verifier="claude-sonnet-4-5-20250929",
        quality_threshold=0.65,
        temperature=0.8,
    ),
    # General fallback - GPT-5 Mini
    "general": DomainBenchmarkConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - fast and capable
        verifier="gpt-5",
        quality_threshold=0.70,
        temperature=0.7,
    ),
}


@dataclass
class BenchmarkConfig:
    """Complete benchmark configuration."""

    # Core settings
    mode: BenchmarkMode = BenchmarkMode.FULL

    # Model selection (2025 GPT-5 family)
    default_drafter: str = "gpt-5-mini"  # $0.25/M input, $2/M output
    default_verifier: str = "gpt-5"  # $1.25/M input, $10/M output
    baseline_model: str = "gpt-5"  # Model for baseline comparison

    # Quality thresholds
    default_quality_threshold: float = 0.70

    # Semantic detection settings
    enable_semantic_detection: bool = True
    semantic_confidence_threshold: float = 0.5

    # Domain pipeline settings
    enable_domain_pipeline: bool = True
    domain_configs: dict[str, DomainBenchmarkConfig] = field(
        default_factory=lambda: DOMAIN_CONFIGS.copy()
    )

    # Cascade thresholds by complexity
    complexity_thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "trivial": 0.55,
            "simple": 0.50,
            "moderate": 0.45,
            "hard": 0.42,
            "expert": 0.40,
        }
    )

    # Benchmark limits
    max_samples: Optional[int] = None
    timeout_seconds: float = 60.0

    @classmethod
    def baseline(cls) -> "BenchmarkConfig":
        """Create baseline configuration (no semantic, no domain pipeline)."""
        return cls(
            mode=BenchmarkMode.BASELINE,
            enable_semantic_detection=False,
            enable_domain_pipeline=False,
        )

    @classmethod
    def semantic_only(cls) -> "BenchmarkConfig":
        """Create semantic-only configuration."""
        return cls(
            mode=BenchmarkMode.SEMANTIC_ONLY,
            enable_semantic_detection=True,
            enable_domain_pipeline=False,
        )

    @classmethod
    def domain_only(cls) -> "BenchmarkConfig":
        """Create domain-pipeline-only configuration."""
        return cls(
            mode=BenchmarkMode.DOMAIN_ONLY,
            enable_semantic_detection=False,
            enable_domain_pipeline=True,
        )

    @classmethod
    def full(cls) -> "BenchmarkConfig":
        """Create full configuration (semantic + domain pipeline)."""
        return cls(
            mode=BenchmarkMode.FULL,
            enable_semantic_detection=True,
            enable_domain_pipeline=True,
        )

    @classmethod
    def for_mtbench(cls, mode: BenchmarkMode = BenchmarkMode.FULL) -> "BenchmarkConfig":
        """Create optimized config for MT-Bench (85% cost reduction target)."""
        config = cls(mode=mode)
        # MT-Bench has diverse categories - use lower thresholds for creative
        config.domain_configs["writing"] = DomainBenchmarkConfig(
            drafter="gpt-4o-mini",
            verifier="gpt-4o",
            quality_threshold=0.60,  # Lower for writing
            temperature=0.7,
        )
        config.domain_configs["roleplay"] = DomainBenchmarkConfig(
            drafter="gpt-4o-mini",
            verifier="gpt-4o",
            quality_threshold=0.60,  # Lower for roleplay
            temperature=0.8,
        )
        return config

    @classmethod
    def for_mmlu(cls, mode: BenchmarkMode = BenchmarkMode.FULL) -> "BenchmarkConfig":
        """Create optimized config for MMLU (45% cost reduction target)."""
        config = cls(mode=mode)
        # MMLU needs higher accuracy - conservative thresholds
        config.default_quality_threshold = 0.75
        config.domain_configs["stem"] = DomainBenchmarkConfig(
            drafter="gpt-4o-mini",
            verifier="gpt-4o",
            quality_threshold=0.80,
            temperature=0.2,
        )
        return config

    @classmethod
    def for_gsm8k(cls, mode: BenchmarkMode = BenchmarkMode.FULL) -> "BenchmarkConfig":
        """Create optimized config for GSM8K (35% cost reduction target)."""
        config = cls(mode=mode)
        # GSM8K is math - highest accuracy needed
        config.default_quality_threshold = 0.85
        config.domain_configs["math"] = DomainBenchmarkConfig(
            drafter="gpt-4o-mini",  # or deepseek-coder for math
            verifier="gpt-4o",
            quality_threshold=0.88,
            temperature=0.1,
        )
        return config

    def get_domain_config(self, domain: str) -> DomainBenchmarkConfig:
        """Get configuration for a specific domain."""
        return self.domain_configs.get(
            domain,
            self.domain_configs.get(
                "general",
                DomainBenchmarkConfig(
                    drafter=self.default_drafter,
                    verifier=self.default_verifier,
                    quality_threshold=self.default_quality_threshold,
                ),
            ),
        )

    def to_agent_config(self) -> dict[str, Any]:
        """Convert to CascadeAgent configuration dict."""
        return {
            "models": [
                {"name": self.default_drafter, "provider": "openai"},
                {"name": self.default_verifier, "provider": "openai"},
            ],
            "enable_domain_detection": self.enable_domain_pipeline,
            "use_semantic_domains": self.enable_semantic_detection,
            "quality_threshold": self.default_quality_threshold,
        }


@dataclass
class BenchmarkTargets:
    """Cost reduction and quality targets for benchmarks."""

    # Cost reduction targets (percentage)
    mt_bench_cost_reduction: float = 85.0  # ≥85%
    mmlu_cost_reduction: float = 45.0  # ≥45%
    gsm8k_cost_reduction: float = 35.0  # ≥35%

    # Quality retention targets (percentage of baseline)
    quality_retention: float = 95.0  # ≥95%

    def check_mt_bench(self, cost_reduction: float, quality_retention: float) -> bool:
        """Check if MT-Bench targets are met."""
        return (
            cost_reduction >= self.mt_bench_cost_reduction
            and quality_retention >= self.quality_retention
        )

    def check_mmlu(self, cost_reduction: float, quality_retention: float) -> bool:
        """Check if MMLU targets are met."""
        return (
            cost_reduction >= self.mmlu_cost_reduction
            and quality_retention >= self.quality_retention
        )

    def check_gsm8k(self, cost_reduction: float, quality_retention: float) -> bool:
        """Check if GSM8K targets are met."""
        return (
            cost_reduction >= self.gsm8k_cost_reduction
            and quality_retention >= self.quality_retention
        )


# Default targets
DEFAULT_TARGETS = BenchmarkTargets()


def print_config(config: BenchmarkConfig) -> None:
    """Print benchmark configuration in a readable format."""
    print(f"\nBenchmark Configuration:")
    print(f"  Mode: {config.mode.value}")
    print(f"  Drafter: {config.default_drafter}")
    print(f"  Verifier: {config.default_verifier}")
    print(f"  Baseline: {config.baseline_model}")
    print(f"  Quality Threshold: {config.default_quality_threshold}")
    print(f"  Semantic Detection: {config.enable_semantic_detection}")
    print(f"  Domain Pipeline: {config.enable_domain_pipeline}")
    if config.enable_domain_pipeline:
        print(f"  Domain Configs:")
        for domain, dc in config.domain_configs.items():
            print(f"    {domain}: threshold={dc.quality_threshold}, temp={dc.temperature}")
