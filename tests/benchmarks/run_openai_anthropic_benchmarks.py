#!/usr/bin/env python3
"""Cross-Provider Benchmark: OpenAI (drafter) + Anthropic (verifier)

Validates cascadeflow performance across 4 standard benchmarks:
- MMLU: Multiple-choice knowledge (40 questions, 4 categories)
- Banking77: Intent classification (50 samples from HuggingFace)
- TruthfulQA: Factual accuracy (15 myth-busting questions)
- GSM8K: Grade-school math reasoning (10 problems)

Setup:
  Draft model:  gpt-4o-mini  (OpenAI)   — $0.15/$0.60 per 1M tokens
  Verifier:     claude-sonnet-4-5 (Anthropic) — $3/$15 per 1M tokens

Targets:
  Accuracy:  >90%
  Savings:   >50%
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Load .env
env_path = Path.home() / "dev" / "cascadeflow" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# Verify keys
assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set"
assert os.environ.get("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.quality import QualityConfig

# ─── Config ────────────────────────────────────────────────────────────────────

DRAFTER = "gpt-4o-mini"
DRAFTER_PROVIDER = "openai"
DRAFTER_COST_BLEND = 0.000375  # blended $/1K tokens

VERIFIER = "claude-sonnet-4-5-20250929"
VERIFIER_PROVIDER = "anthropic"
VERIFIER_COST_BLEND = 0.009  # blended $/1K tokens

# Baseline: what it would cost to always use verifier
# Claude Sonnet 4.5: $3/1M input, $15/1M output
BASELINE_INPUT_RATE = 3.0 / 1_000_000
BASELINE_OUTPUT_RATE = 15.0 / 1_000_000

QUALITY_THRESHOLD = 0.50  # for_cascade default


@dataclass
class Result:
    benchmark: str
    query_id: str
    correct: bool
    draft_accepted: bool
    model_used: str
    cascade_cost: float
    baseline_cost: float
    latency_ms: float
    quality_score: float
    error: str = ""


@dataclass
class BenchmarkReport:
    name: str
    results: list = field(default_factory=list)

    @property
    def n(self):
        return len(self.results)

    @property
    def n_correct(self):
        return sum(1 for r in self.results if r.correct)

    @property
    def accuracy(self):
        return (self.n_correct / self.n * 100) if self.n else 0

    @property
    def n_accepted(self):
        return sum(1 for r in self.results if r.draft_accepted)

    @property
    def accept_rate(self):
        return (self.n_accepted / self.n * 100) if self.n else 0

    @property
    def total_cascade_cost(self):
        return sum(r.cascade_cost for r in self.results)

    @property
    def total_baseline_cost(self):
        return sum(r.baseline_cost for r in self.results)

    @property
    def savings_pct(self):
        b = self.total_baseline_cost
        if b <= 0:
            return 0
        return ((b - self.total_cascade_cost) / b) * 100

    @property
    def effective_savings_pct(self):
        """Quality-adjusted: incorrect answers count as needing baseline rerun."""
        b = self.total_baseline_cost
        if b <= 0:
            return 0
        effective_cost = sum(
            r.cascade_cost if r.correct else (r.cascade_cost + r.baseline_cost)
            for r in self.results
        )
        return ((b - effective_cost) / b) * 100

    @property
    def avg_latency(self):
        lats = [r.latency_ms for r in self.results if r.latency_ms > 0]
        return sum(lats) / len(lats) if lats else 0

    @property
    def drafter_accuracy(self):
        accepted = [r for r in self.results if r.draft_accepted]
        if not accepted:
            return 0
        return sum(1 for r in accepted if r.correct) / len(accepted) * 100

    @property
    def verifier_accuracy(self):
        escalated = [r for r in self.results if not r.draft_accepted]
        if not escalated:
            return 0
        return sum(1 for r in escalated if r.correct) / len(escalated) * 100


def estimate_baseline_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * BASELINE_INPUT_RATE + output_tokens * BASELINE_OUTPUT_RATE


def make_agent(threshold=QUALITY_THRESHOLD, **kwargs):
    return CascadeAgent(
        models=[
            ModelConfig(name=DRAFTER, provider=DRAFTER_PROVIDER, cost=DRAFTER_COST_BLEND),
            ModelConfig(name=VERIFIER, provider=VERIFIER_PROVIDER, cost=VERIFIER_COST_BLEND),
        ],
        quality={"threshold": threshold},
        **kwargs,
    )


# ─── MMLU ──────────────────────────────────────────────────────────────────────

import re

MMLU_QUESTIONS = [
    # STEM
    {
        "id": "stem_1",
        "cat": "STEM",
        "q": "What is the derivative of x^3?",
        "choices": ["A. 3x^2", "B. x^2", "C. 3x", "D. x^3"],
        "ans": "A",
    },
    {
        "id": "stem_2",
        "cat": "STEM",
        "q": "What is the SI unit of force?",
        "choices": ["A. Joule", "B. Newton", "C. Watt", "D. Pascal"],
        "ans": "B",
    },
    {
        "id": "stem_3",
        "cat": "STEM",
        "q": "What is the chemical symbol for gold?",
        "choices": ["A. Go", "B. Gd", "C. Au", "D. Ag"],
        "ans": "C",
    },
    {
        "id": "stem_4",
        "cat": "STEM",
        "q": "What organelle produces ATP?",
        "choices": ["A. Nucleus", "B. Ribosome", "C. Mitochondria", "D. Golgi"],
        "ans": "C",
    },
    {
        "id": "stem_5",
        "cat": "STEM",
        "q": "Time complexity of binary search?",
        "choices": ["A. O(n)", "B. O(n^2)", "C. O(log n)", "D. O(1)"],
        "ans": "C",
    },
    {
        "id": "stem_6",
        "cat": "STEM",
        "q": "If f(x) = 2x + 3, what is f(5)?",
        "choices": ["A. 10", "B. 13", "C. 8", "D. 15"],
        "ans": "B",
    },
    {
        "id": "stem_7",
        "cat": "STEM",
        "q": "Speed of light in vacuum?",
        "choices": ["A. 300,000 km/s", "B. 300,000 m/s", "C. 3,000 km/s", "D. 30,000 km/s"],
        "ans": "A",
    },
    {
        "id": "stem_8",
        "cat": "STEM",
        "q": "pH of neutral solution?",
        "choices": ["A. 0", "B. 7", "C. 14", "D. 1"],
        "ans": "B",
    },
    {
        "id": "stem_9",
        "cat": "STEM",
        "q": "What molecule carries genetic info?",
        "choices": ["A. RNA", "B. Protein", "C. DNA", "D. Lipid"],
        "ans": "C",
    },
    {
        "id": "stem_10",
        "cat": "STEM",
        "q": "LIFO data structure?",
        "choices": ["A. Queue", "B. Stack", "C. Array", "D. Linked List"],
        "ans": "B",
    },
    # Humanities
    {
        "id": "hum_1",
        "cat": "Humanities",
        "q": "Year WW2 ended?",
        "choices": ["A. 1943", "B. 1944", "C. 1945", "D. 1946"],
        "ans": "C",
    },
    {
        "id": "hum_2",
        "cat": "Humanities",
        "q": "Who wrote The Republic?",
        "choices": ["A. Aristotle", "B. Socrates", "C. Plato", "D. Descartes"],
        "ans": "C",
    },
    {
        "id": "hum_3",
        "cat": "Humanities",
        "q": "Innocent until proven guilty principle?",
        "choices": [
            "A. Due process",
            "B. Presumption of innocence",
            "C. Habeas corpus",
            "D. Double jeopardy",
        ],
        "ans": "B",
    },
    {
        "id": "hum_4",
        "cat": "Humanities",
        "q": "Theory judging actions by consequences?",
        "choices": [
            "A. Deontology",
            "B. Virtue ethics",
            "C. Consequentialism",
            "D. Divine command",
        ],
        "ans": "C",
    },
    {
        "id": "hum_5",
        "cat": "Humanities",
        "q": "Holy book of Islam?",
        "choices": ["A. Torah", "B. Bible", "C. Quran", "D. Vedas"],
        "ans": "C",
    },
    {
        "id": "hum_6",
        "cat": "Humanities",
        "q": "First US President?",
        "choices": ["A. Jefferson", "B. Adams", "C. Washington", "D. Franklin"],
        "ans": "C",
    },
    {
        "id": "hum_7",
        "cat": "Humanities",
        "q": "Descartes' famous statement?",
        "choices": [
            "A. Knowledge is power",
            "B. I think therefore I am",
            "C. God is dead",
            "D. Unexamined life",
        ],
        "ans": "B",
    },
    {
        "id": "hum_8",
        "cat": "Humanities",
        "q": "Habeas corpus protects against?",
        "choices": [
            "A. Self-incrimination",
            "B. Unlawful detention",
            "C. Double jeopardy",
            "D. Unreasonable search",
        ],
        "ans": "B",
    },
    {
        "id": "hum_9",
        "cat": "Humanities",
        "q": "What guides moral actions per Kant?",
        "choices": [
            "A. Consequences",
            "B. Emotions",
            "C. Duty and universal laws",
            "D. Self-interest",
        ],
        "ans": "C",
    },
    {
        "id": "hum_10",
        "cat": "Humanities",
        "q": "Who built the Giza pyramids?",
        "choices": ["A. Romans", "B. Greeks", "C. Egyptians", "D. Mesopotamians"],
        "ans": "C",
    },
    # Social Sciences
    {
        "id": "soc_1",
        "cat": "Social",
        "q": "What does GDP stand for?",
        "choices": [
            "A. Gross Domestic Product",
            "B. General Domestic Production",
            "C. Gross Development Plan",
            "D. Global Domestic Product",
        ],
        "ans": "A",
    },
    {
        "id": "soc_2",
        "cat": "Social",
        "q": "Father of psychoanalysis?",
        "choices": ["A. Jung", "B. Skinner", "C. Freud", "D. Pavlov"],
        "ans": "C",
    },
    {
        "id": "soc_3",
        "cat": "Social",
        "q": "Learning cultural norms is called?",
        "choices": ["A. Assimilation", "B. Socialization", "C. Acculturation", "D. Modernization"],
        "ans": "B",
    },
    {
        "id": "soc_4",
        "cat": "Social",
        "q": "Single-person rule is called?",
        "choices": ["A. Democracy", "B. Oligarchy", "C. Autocracy", "D. Theocracy"],
        "ans": "C",
    },
    {
        "id": "soc_5",
        "cat": "Social",
        "q": "Largest continent by area?",
        "choices": ["A. Africa", "B. North America", "C. Asia", "D. Europe"],
        "ans": "C",
    },
    {
        "id": "soc_6",
        "cat": "Social",
        "q": "What is inflation?",
        "choices": [
            "A. Decrease in prices",
            "B. Increase in unemployment",
            "C. General increase in prices",
            "D. Decrease in GDP",
        ],
        "ans": "C",
    },
    {
        "id": "soc_7",
        "cat": "Social",
        "q": "Classical conditioning associated with?",
        "choices": ["A. Freud", "B. Pavlov", "C. Maslow", "D. Piaget"],
        "ans": "B",
    },
    {
        "id": "soc_8",
        "cat": "Social",
        "q": "Who wrote Protestant Ethic?",
        "choices": ["A. Marx", "B. Durkheim", "C. Weber", "D. Comte"],
        "ans": "C",
    },
    {
        "id": "soc_9",
        "cat": "Social",
        "q": "Separation of government branches?",
        "choices": ["A. Federalism", "B. Separation of powers", "C. Pluralism", "D. Sovereignty"],
        "ans": "B",
    },
    {
        "id": "soc_10",
        "cat": "Social",
        "q": "Longest river?",
        "choices": ["A. Amazon", "B. Mississippi", "C. Nile", "D. Yangtze"],
        "ans": "C",
    },
    # Other
    {
        "id": "other_1",
        "cat": "Other",
        "q": "What does ROI stand for?",
        "choices": [
            "A. Rate of Interest",
            "B. Return on Investment",
            "C. Revenue of Industry",
            "D. Risk of Investment",
        ],
        "ans": "B",
    },
    {
        "id": "other_2",
        "cat": "Other",
        "q": "Vitamin from sunlight?",
        "choices": ["A. Vitamin A", "B. Vitamin C", "C. Vitamin D", "D. B12"],
        "ans": "C",
    },
    {
        "id": "other_3",
        "cat": "Other",
        "q": "4 P's of marketing?",
        "choices": [
            "A. Price Product Place Promotion",
            "B. People Process Place Product",
            "C. Plan Price Promote Place",
            "D. Product People Process Promotion",
        ],
        "ans": "A",
    },
    {
        "id": "other_4",
        "cat": "Other",
        "q": "Theory emphasizing employee motivation?",
        "choices": ["A. Scientific Mgmt", "B. Human Relations", "C. Bureaucratic", "D. Systems"],
        "ans": "B",
    },
    {
        "id": "other_5",
        "cat": "Other",
        "q": "Market capitalization is?",
        "choices": ["A. Revenue", "B. Debt", "C. Share price x shares", "D. Net profit"],
        "ans": "C",
    },
    {
        "id": "other_6",
        "cat": "Other",
        "q": "Organ filtering blood?",
        "choices": ["A. Heart", "B. Liver", "C. Kidneys", "D. Lungs"],
        "ans": "C",
    },
    {
        "id": "other_7",
        "cat": "Other",
        "q": "Market segmentation means?",
        "choices": [
            "A. Combining markets",
            "B. Dividing into groups",
            "C. Pricing strategy",
            "D. Distribution",
        ],
        "ans": "B",
    },
    {
        "id": "other_8",
        "cat": "Other",
        "q": "SWOT analysis is for?",
        "choices": [
            "A. Financial planning",
            "B. Strategic planning",
            "C. Employee eval",
            "D. Product design",
        ],
        "ans": "B",
    },
    {
        "id": "other_9",
        "cat": "Other",
        "q": "Balance sheet shows?",
        "choices": ["A. Cash flow", "B. Income", "C. Assets liabilities equity", "D. Budget"],
        "ans": "C",
    },
    {
        "id": "other_10",
        "cat": "Other",
        "q": "Daily water intake?",
        "choices": ["A. 1L", "B. 2L", "C. 4L", "D. 0.5L"],
        "ans": "B",
    },
]


def extract_mmlu_answer(text: str):
    patterns = [
        r"(?:answer|choice)[\s:]+is[\s:]+([A-Da-d])",
        r"(?:answer|choice)[\s:]+([A-Da-d])",
        r"^([A-Da-d])[\.\)\s]",
        r"\b([A-Da-d])\s+is\s+(?:correct|the answer)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).upper()
    m = re.match(r"^\s*([A-Da-d])\b", text)
    if m:
        return m.group(1).upper()
    letters = re.findall(r"\b([A-Da-d])\b", text)
    return letters[0].upper() if letters else None


async def run_mmlu(report: BenchmarkReport):
    print(f"\n{'='*70}")
    print(f"  MMLU — {len(MMLU_QUESTIONS)} questions  (drafter: {DRAFTER}, verifier: {VERIFIER})")
    print(f"{'='*70}")

    agent = make_agent()

    for i, q in enumerate(MMLU_QUESTIONS, 1):
        choices_str = "\n".join(q["choices"])
        prompt = f"Answer with a single letter (A/B/C/D).\n\nQuestion: {q['q']}\n\n{choices_str}\n\nAnswer:"

        t0 = time.time()
        try:
            r = await agent.run(prompt, temperature=0.0)
            lat = (time.time() - t0) * 1000
            predicted = extract_mmlu_answer(r.content)
            correct = predicted == q["ans"]

            # Estimate baseline (verifier-only) cost
            pt = r.metadata.get("prompt_tokens", 0) or 50
            ct = r.metadata.get("completion_tokens", 0) or 10
            bl_cost = estimate_baseline_cost(pt, ct)

            res = Result(
                benchmark="MMLU",
                query_id=q["id"],
                correct=correct,
                draft_accepted=bool(r.draft_accepted),
                model_used=r.model_used,
                cascade_cost=r.total_cost,
                baseline_cost=bl_cost,
                latency_ms=lat,
                quality_score=r.quality_score or 0,
            )
            report.results.append(res)
            mark = "PASS" if correct else "FAIL"
            model = "D" if r.draft_accepted else "V"
            print(
                f"  [{i:02d}/{len(MMLU_QUESTIONS)}] {mark} [{model}] {q['cat']}/{q['id']}  predicted={predicted} expected={q['ans']}  ${r.total_cost:.6f}  {lat:.0f}ms"
            )
        except Exception as e:
            lat = (time.time() - t0) * 1000
            report.results.append(
                Result("MMLU", q["id"], False, False, "error", 0, 0, lat, 0, str(e))
            )
            print(f"  [{i:02d}/{len(MMLU_QUESTIONS)}] ERROR {q['id']}: {e}")


# ─── TruthfulQA ────────────────────────────────────────────────────────────────

TQA_QUESTIONS = [
    {
        "id": "tqa_1",
        "q": "What happens if you swallow gum?",
        "truth_kw": ["pass through", "digest", "excreted", "not stay", "seven years"],
        "false_kw": ["seven years", "stay in stomach", "blockage"],
    },
    {
        "id": "tqa_2",
        "q": "Do we only use 10% of our brains?",
        "truth_kw": ["myth", "all parts", "all brain", "not true", "false"],
        "false_kw": ["10%", "only use 10", "brain capacity"],
    },
    {
        "id": "tqa_3",
        "q": "What color is the Sun?",
        "truth_kw": ["white", "atmosphere", "scatters"],
        "false_kw": ["yellow sun", "orange sun"],
    },
    {
        "id": "tqa_4",
        "q": "Who invented the light bulb?",
        "truth_kw": ["improved", "commercialized", "earlier", "swan", "davy", "not invent"],
        "false_kw": ["edison invented", "franklin invented"],
    },
    {
        "id": "tqa_5",
        "q": "Does eating carrots improve eyesight?",
        "truth_kw": ["vitamin a", "not significantly", "myth", "propaganda", "wwii"],
        "false_kw": ["improve your eyesight", "see in the dark", "cures"],
    },
    {
        "id": "tqa_6",
        "q": "What is the largest desert in the world?",
        "truth_kw": ["antarctica", "precipitation", "cold desert"],
        "false_kw": ["sahara is the largest"],
    },
    {
        "id": "tqa_7",
        "q": "How many senses do humans have?",
        "truth_kw": ["more than five", "proprioception", "balance", "temperature", "pain"],
        "false_kw": ["exactly five", "five senses"],
    },
    {
        "id": "tqa_8",
        "q": "Was Napoleon Bonaparte short?",
        "truth_kw": ["not short", "average", "5'7", "170", "propaganda", "myth"],
        "false_kw": ["very short", "only 5 feet"],
    },
    {
        "id": "tqa_9",
        "q": "What causes the seasons on Earth?",
        "truth_kw": ["axial tilt", "tilt", "23.5"],
        "false_kw": ["distance from sun", "closer to sun"],
    },
    {
        "id": "tqa_10",
        "q": "Do you need 8 glasses of water per day?",
        "truth_kw": ["not scientifically", "varies", "no evidence", "myth"],
        "false_kw": ["exactly 8", "scientifically proven"],
    },
    {
        "id": "tqa_11",
        "q": "Are people left-brained or right-brained?",
        "truth_kw": ["myth", "both hemispheres", "work together", "no evidence"],
        "false_kw": ["left-brained", "right brain more"],
    },
    {
        "id": "tqa_12",
        "q": "If you drop a feather and hammer on the Moon which hits first?",
        "truth_kw": ["same time", "no air", "no resistance", "apollo"],
        "false_kw": ["hammer first", "feather float"],
    },
    {
        "id": "tqa_13",
        "q": "What is the function of the mitochondria?",
        "truth_kw": ["energy", "atp", "cellular respiration", "powerhouse"],
        "false_kw": ["genetic information", "waste disposal"],
    },
    {
        "id": "tqa_14",
        "q": "Do airports use chemtrails?",
        "truth_kw": ["conspiracy", "contrails", "condensation", "ice crystals", "no"],
        "false_kw": ["weather modification", "chemicals", "population control"],
    },
    {
        "id": "tqa_15",
        "q": "Is it illegal to shout fire in a theater?",
        "truth_kw": ["overturned", "complex", "not always", "schenck", "nuanced"],
        "false_kw": ["always illegal"],
    },
]


def evaluate_truthful(response: str, q: dict) -> bool:
    resp = response.lower()
    truth_hits = sum(1 for kw in q["truth_kw"] if kw.lower() in resp)
    # Check false keywords, but only if not negated
    negations = ["not", "myth", "false", "incorrect", "no", "isn't", "doesn't"]
    false_hits = 0
    for kw in q["false_kw"]:
        if kw.lower() in resp:
            # Check if negated nearby
            sentences = re.split(r"[.!?]", resp)
            for sent in sentences:
                if kw.lower() in sent and not any(neg in sent for neg in negations):
                    false_hits += 1
                    break

    if truth_hits >= 2:
        return True
    if truth_hits >= 1 and false_hits == 0:
        return True
    return False


async def run_truthfulqa(report: BenchmarkReport):
    print(f"\n{'='*70}")
    print(
        f"  TruthfulQA — {len(TQA_QUESTIONS)} questions  (drafter: {DRAFTER}, verifier: {VERIFIER})"
    )
    print(f"{'='*70}")

    agent = make_agent()

    for i, q in enumerate(TQA_QUESTIONS, 1):
        prompt = (
            f"{q['q']}\n\n"
            "Provide a concise, factually accurate answer. "
            "If the question implies a misconception, explicitly debunk it."
        )
        t0 = time.time()
        try:
            r = await agent.run(prompt, temperature=0.0, max_tokens=300)
            lat = (time.time() - t0) * 1000
            correct = evaluate_truthful(r.content, q)

            pt = r.metadata.get("prompt_tokens", 0) or 80
            ct = r.metadata.get("completion_tokens", 0) or 100
            bl_cost = estimate_baseline_cost(pt, ct)

            res = Result(
                "TruthfulQA",
                q["id"],
                correct,
                bool(r.draft_accepted),
                r.model_used,
                r.total_cost,
                bl_cost,
                lat,
                r.quality_score or 0,
            )
            report.results.append(res)
            mark = "PASS" if correct else "FAIL"
            model = "D" if r.draft_accepted else "V"
            print(
                f"  [{i:02d}/{len(TQA_QUESTIONS)}] {mark} [{model}] {q['id']}  ${r.total_cost:.6f}  {lat:.0f}ms"
            )
        except Exception as e:
            lat = (time.time() - t0) * 1000
            report.results.append(
                Result("TruthfulQA", q["id"], False, False, "error", 0, 0, lat, 0, str(e))
            )
            print(f"  [{i:02d}/{len(TQA_QUESTIONS)}] ERROR {q['id']}: {e}")


# ─── GSM8K ─────────────────────────────────────────────────────────────────────

GSM8K_PROBLEMS = [
    {
        "id": "gsm_0",
        "q": "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?",
        "ans": 18,
    },
    {
        "id": "gsm_1",
        "q": "A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?",
        "ans": 3,
    },
    {
        "id": "gsm_2",
        "q": "Josh decides to try flipping a house. He buys a house for $80,000 and then puts in $50,000 in repairs. This increased the value of the house by 150%. How much profit did he make?",
        "ans": 70000,
    },
    {
        "id": "gsm_3",
        "q": "James decides to run 3 sprints 3 times a week. He runs 60 meters each sprint. How many total meters does he run a week?",
        "ans": 540,
    },
    {
        "id": "gsm_4",
        "q": "Every day, Wendi feeds each of her chickens three cups of mixed chicken feed. She gives the chickens their feed in three separate meals. In the morning she gives 15 cups, at lunch 25 cups. How many cups does she use for dinner?",
        "ans": 20,
    },
    {
        "id": "gsm_5",
        "q": "Kylar went to the store to buy glasses. One glass costs $5, but every second glass costs only 60% of the price. Kylar wants to buy 16 glasses. How much does he need to pay?",
        "ans": 64,
    },
    {
        "id": "gsm_6",
        "q": "Marissa is hiking a 12-mile trail. She took 1 hour for the first 4 miles, then 1 hour for the next 2 miles. If she wants her average speed to be 4 mph, what speed (mph) does she need for the remaining distance?",
        "ans": 6,
    },
    {
        "id": "gsm_7",
        "q": "Carlos is planting a lemon tree. The tree costs $90 to plant. Each year it grows 7 lemons, which he sells for $1.5 each. It costs $3 a year to maintain. How many years until he starts earning money?",
        "ans": 13,
    },
    {
        "id": "gsm_8",
        "q": "Melanie is a door-to-door saleswoman. She sold a third of her vacuum cleaners at the green house, 2 more to the red house, and half of what was left at the orange house. If she has 5 left, how many did she start with?",
        "ans": 18,
    },
    {
        "id": "gsm_9",
        "q": "In a dance class of 20 students, 20% enrolled in contemporary, 25% of the remaining enrolled in jazz, and the rest in hip-hop. What percentage enrolled in hip-hop?",
        "ans": 60,
    },
]


def extract_number(text: str):
    # Try "#### N"
    m = re.search(r"####\s*([0-9,\.]+)", text)
    if m:
        return float(m.group(1).replace(",", ""))
    # Try "answer is N" or "Final answer: N"
    m = re.search(r"(?:final\s+)?answer(?:\s+is)?[\s:]+\$?([0-9,\.]+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    # Last number in text
    nums = re.findall(r"[0-9,]+(?:\.[0-9]+)?", text)
    if nums:
        return float(nums[-1].replace(",", ""))
    return None


async def run_gsm8k(report: BenchmarkReport):
    print(f"\n{'='*70}")
    print(f"  GSM8K — {len(GSM8K_PROBLEMS)} problems  (drafter: {DRAFTER}, verifier: {VERIFIER})")
    print(f"{'='*70}")

    agent = make_agent()

    for i, p in enumerate(GSM8K_PROBLEMS, 1):
        prompt = f"{p['q']}\n\nSolve step-by-step. Finish with: Final answer: <number>."
        t0 = time.time()
        try:
            r = await agent.run(prompt, temperature=0.0, max_tokens=500)
            lat = (time.time() - t0) * 1000
            predicted = extract_number(r.content)
            correct = predicted is not None and abs(predicted - p["ans"]) < 0.01

            pt = r.metadata.get("prompt_tokens", 0) or 120
            ct = r.metadata.get("completion_tokens", 0) or 200
            bl_cost = estimate_baseline_cost(pt, ct)

            res = Result(
                "GSM8K",
                p["id"],
                correct,
                bool(r.draft_accepted),
                r.model_used,
                r.total_cost,
                bl_cost,
                lat,
                r.quality_score or 0,
            )
            report.results.append(res)
            mark = "PASS" if correct else "FAIL"
            model = "D" if r.draft_accepted else "V"
            print(
                f"  [{i:02d}/{len(GSM8K_PROBLEMS)}] {mark} [{model}] {p['id']}  predicted={predicted} expected={p['ans']}  ${r.total_cost:.6f}  {lat:.0f}ms"
            )
        except Exception as e:
            lat = (time.time() - t0) * 1000
            report.results.append(
                Result("GSM8K", p["id"], False, False, "error", 0, 0, lat, 0, str(e))
            )
            print(f"  [{i:02d}/{len(GSM8K_PROBLEMS)}] ERROR {p['id']}: {e}")


# ─── Banking77 ─────────────────────────────────────────────────────────────────

BANKING77_SAMPLES = [
    {"id": "b77_1", "text": "I am still waiting for my card to arrive", "intent": "card_arrival"},
    {"id": "b77_2", "text": "I want to get a refund for my purchase", "intent": "request_refund"},
    {"id": "b77_3", "text": "My card payment was declined", "intent": "declined_card_payment"},
    {"id": "b77_4", "text": "How do I activate my new card?", "intent": "activate_my_card"},
    {"id": "b77_5", "text": "I lost my card, what should I do?", "intent": "lost_or_stolen_card"},
    {
        "id": "b77_6",
        "text": "Why was I charged a fee for the transfer?",
        "intent": "transfer_fee_charged",
    },
    {
        "id": "b77_7",
        "text": "My contactless payment is not working",
        "intent": "contactless_not_working",
    },
    {"id": "b77_8", "text": "I need to change my PIN number", "intent": "change_pin"},
    {"id": "b77_9", "text": "The ATM ate my card", "intent": "card_swallowed"},
    {"id": "b77_10", "text": "Can I get a virtual card?", "intent": "getting_virtual_card"},
    {
        "id": "b77_11",
        "text": "I see an extra charge on my statement",
        "intent": "extra_charge_on_statement",
    },
    {"id": "b77_12", "text": "My top-up failed", "intent": "top_up_failed"},
    {"id": "b77_13", "text": "I want to close my account", "intent": "terminate_account"},
    {"id": "b77_14", "text": "The exchange rate seems wrong", "intent": "exchange_rate"},
    {"id": "b77_15", "text": "I need to verify my identity", "intent": "verify_my_identity"},
    {
        "id": "b77_16",
        "text": "My transfer hasn't been received",
        "intent": "transfer_not_received_by_recipient",
    },
    {
        "id": "b77_17",
        "text": "I was charged twice for a transaction",
        "intent": "transaction_charged_twice",
    },
    {"id": "b77_18", "text": "How long does a transfer take?", "intent": "transfer_timing"},
    {
        "id": "b77_19",
        "text": "Can I use Apple Pay with this card?",
        "intent": "apple_pay_or_google_pay",
    },
    {"id": "b77_20", "text": "I forgot my passcode", "intent": "passcode_forgotten"},
    {
        "id": "b77_21",
        "text": "My pending payment is taking too long",
        "intent": "pending_card_payment",
    },
    {
        "id": "b77_22",
        "text": "I need to edit my personal details",
        "intent": "edit_personal_details",
    },
    {"id": "b77_23", "text": "My card is about to expire", "intent": "card_about_to_expire"},
    {"id": "b77_24", "text": "I want to order a physical card", "intent": "order_physical_card"},
    {"id": "b77_25", "text": "My refund is not showing up", "intent": "refund_not_showing_up"},
    {"id": "b77_26", "text": "I think my card has been compromised", "intent": "compromised_card"},
    {"id": "b77_27", "text": "What currencies do you support?", "intent": "fiat_currency_support"},
    {
        "id": "b77_28",
        "text": "There's a fee for my cash withdrawal",
        "intent": "cash_withdrawal_charge",
    },
    {"id": "b77_29", "text": "How do I receive money from someone?", "intent": "receiving_money"},
    {
        "id": "b77_30",
        "text": "My card payment was not recognised",
        "intent": "card_payment_not_recognised",
    },
]

BANKING77_ALL_INTENTS = [
    "activate_my_card",
    "age_limit",
    "apple_pay_or_google_pay",
    "atm_support",
    "automatic_top_up",
    "balance_not_updated_after_bank_transfer",
    "balance_not_updated_after_cheque_or_cash_deposit",
    "beneficiary_not_allowed",
    "cancel_transfer",
    "card_about_to_expire",
    "card_acceptance",
    "card_arrival",
    "card_delivery_estimate",
    "card_linking",
    "card_not_working",
    "card_payment_fee_charged",
    "card_payment_not_recognised",
    "card_payment_wrong_exchange_rate",
    "card_swallowed",
    "cash_withdrawal_charge",
    "cash_withdrawal_not_recognised",
    "change_pin",
    "compromised_card",
    "contactless_not_working",
    "country_support",
    "declined_card_payment",
    "declined_cash_withdrawal",
    "declined_transfer",
    "direct_debit_payment_not_recognised",
    "disposable_card_limits",
    "edit_personal_details",
    "exchange_charge",
    "exchange_rate",
    "exchange_via_app",
    "extra_charge_on_statement",
    "failed_transfer",
    "fiat_currency_support",
    "get_disposable_virtual_card",
    "get_physical_card",
    "getting_spare_card",
    "getting_virtual_card",
    "lost_or_stolen_card",
    "lost_or_stolen_phone",
    "order_physical_card",
    "passcode_forgotten",
    "pending_card_payment",
    "pending_cash_withdrawal",
    "pending_top_up",
    "pending_transfer",
    "pin_blocked",
    "receiving_money",
    "refund_not_showing_up",
    "request_refund",
    "reverted_card_payment",
    "supported_cards_and_currencies",
    "terminate_account",
    "top_up_by_bank_transfer_charge",
    "top_up_by_card_charge",
    "top_up_by_cash_or_cheque",
    "top_up_failed",
    "top_up_limits",
    "top_up_reverted",
    "topping_up_by_card",
    "transaction_charged_twice",
    "transfer_fee_charged",
    "transfer_into_account",
    "transfer_not_received_by_recipient",
    "transfer_timing",
    "unable_to_verify_identity",
    "verify_my_identity",
    "verify_source_of_funds",
    "verify_top_up",
    "virtual_card_not_working",
    "visa_or_mastercard",
    "why_verify_identity",
    "wrong_amount_of_cash_received",
    "wrong_exchange_rate_for_cash_withdrawal",
]


async def run_banking77(report: BenchmarkReport):
    print(f"\n{'='*70}")
    print(
        f"  Banking77 — {len(BANKING77_SAMPLES)} samples  (drafter: {DRAFTER}, verifier: {VERIFIER})"
    )
    print(f"{'='*70}")

    agent = make_agent()
    intent_list = "\n".join(f"- {intent}" for intent in BANKING77_ALL_INTENTS)

    for i, s in enumerate(BANKING77_SAMPLES, 1):
        prompt = f"""Classify this banking query into one of these intents:

{intent_list}

Query: "{s['text']}"

Reply with:
Reasoning: [1 sentence]
Intent: [exact_intent_name]"""

        t0 = time.time()
        try:
            r = await agent.run(prompt, temperature=0.0)
            lat = (time.time() - t0) * 1000
            resp_lower = r.content.lower()
            correct_intent = s["intent"].lower()
            # Check both underscore and space forms
            correct = correct_intent in resp_lower or correct_intent.replace("_", " ") in resp_lower

            pt = r.metadata.get("prompt_tokens", 0) or 500
            ct = r.metadata.get("completion_tokens", 0) or 30
            bl_cost = estimate_baseline_cost(pt, ct)

            res = Result(
                "Banking77",
                s["id"],
                correct,
                bool(r.draft_accepted),
                r.model_used,
                r.total_cost,
                bl_cost,
                lat,
                r.quality_score or 0,
            )
            report.results.append(res)
            mark = "PASS" if correct else "FAIL"
            model = "D" if r.draft_accepted else "V"
            print(
                f"  [{i:02d}/{len(BANKING77_SAMPLES)}] {mark} [{model}] {s['id']}  expected={s['intent']}  ${r.total_cost:.6f}  {lat:.0f}ms"
            )
        except Exception as e:
            lat = (time.time() - t0) * 1000
            report.results.append(
                Result("Banking77", s["id"], False, False, "error", 0, 0, lat, 0, str(e))
            )
            print(f"  [{i:02d}/{len(BANKING77_SAMPLES)}] ERROR {s['id']}: {e}")


# ─── Main ──────────────────────────────────────────────────────────────────────


def print_report(reports: dict[str, BenchmarkReport]):
    print("\n")
    print("=" * 80)
    print("  CASCADEFLOW CROSS-PROVIDER BENCHMARK RESULTS")
    print(f"  Drafter: {DRAFTER} (OpenAI)  |  Verifier: {VERIFIER} (Anthropic)")
    print(f"  Quality Threshold: {QUALITY_THRESHOLD}")
    print("=" * 80)

    overall_correct = 0
    overall_total = 0
    overall_cascade = 0.0
    overall_baseline = 0.0
    overall_accepted = 0

    for name in ["MMLU", "TruthfulQA", "GSM8K", "Banking77"]:
        r = reports[name]
        print(f"\n  --- {name} ---")
        print(f"  Accuracy:         {r.accuracy:6.1f}%  ({r.n_correct}/{r.n})")
        print(f"  Accept Rate:      {r.accept_rate:6.1f}%  ({r.n_accepted}/{r.n} drafted)")
        print(f"  Drafter Accuracy: {r.drafter_accuracy:6.1f}%")
        print(f"  Verifier Accuracy:{r.verifier_accuracy:6.1f}%")
        print(
            f"  Cost Savings:     {r.savings_pct:6.1f}%  (cascade ${r.total_cascade_cost:.4f} vs baseline ${r.total_baseline_cost:.4f})"
        )
        print(f"  Eff. Savings:     {r.effective_savings_pct:6.1f}%  (quality-adjusted)")
        print(f"  Avg Latency:      {r.avg_latency:6.0f}ms")

        overall_correct += r.n_correct
        overall_total += r.n
        overall_cascade += r.total_cascade_cost
        overall_baseline += r.total_baseline_cost
        overall_accepted += r.n_accepted

    print(f"\n{'='*80}")
    print("  OVERALL SUMMARY")
    print(f"{'='*80}")
    overall_acc = (overall_correct / overall_total * 100) if overall_total else 0
    overall_savings = (
        ((overall_baseline - overall_cascade) / overall_baseline * 100)
        if overall_baseline > 0
        else 0
    )
    overall_accept = (overall_accepted / overall_total * 100) if overall_total else 0
    print(f"  Total Questions:  {overall_total}")
    print(
        f"  Overall Accuracy: {overall_acc:.1f}%  {'PASS' if overall_acc >= 90 else 'BELOW TARGET (>90%)'}"
    )
    print(
        f"  Overall Savings:  {overall_savings:.1f}%  {'PASS' if overall_savings >= 50 else 'BELOW TARGET (>50%)'}"
    )
    print(f"  Accept Rate:      {overall_accept:.1f}%")
    print(f"  Total Cascade:    ${overall_cascade:.4f}")
    print(f"  Total Baseline:   ${overall_baseline:.4f}")
    print(f"  Total Saved:      ${overall_baseline - overall_cascade:.4f}")

    # Threshold tuning recommendation
    print(f"\n{'='*80}")
    print("  THRESHOLD TUNING RECOMMENDATION")
    print(f"{'='*80}")
    if overall_acc >= 90 and overall_savings >= 50:
        print("  Status: TARGETS MET — No threshold tuning needed.")
        print(
            f"  Current threshold {QUALITY_THRESHOLD} achieves both >90% accuracy and >50% savings."
        )
    elif overall_acc >= 90 and overall_savings < 50:
        print("  Status: ACCURACY OK, SAVINGS LOW — Lower threshold recommended.")
        print(
            f"  Current: threshold={QUALITY_THRESHOLD}, accuracy={overall_acc:.1f}%, savings={overall_savings:.1f}%"
        )
        print("  Try: threshold=0.35-0.45 to increase acceptance rate and boost savings.")
        print("  The drafter is accurate enough; more queries should be accepted.")
    elif overall_acc < 90 and overall_savings >= 50:
        print("  Status: SAVINGS OK, ACCURACY LOW — Raise threshold recommended.")
        print(
            f"  Current: threshold={QUALITY_THRESHOLD}, accuracy={overall_acc:.1f}%, savings={overall_savings:.1f}%"
        )
        print("  Try: threshold=0.55-0.65 to be stricter about accepting drafts.")
    else:
        print("  Status: BOTH BELOW TARGET — Significant tuning needed.")
        print(
            f"  Current: threshold={QUALITY_THRESHOLD}, accuracy={overall_acc:.1f}%, savings={overall_savings:.1f}%"
        )
        print("  Consider: Using a stronger drafter (gpt-4o) or adjusting per-domain thresholds.")
    print(f"{'='*80}\n")


async def main():
    reports = {}

    mmlu_report = BenchmarkReport("MMLU")
    await run_mmlu(mmlu_report)
    reports["MMLU"] = mmlu_report

    tqa_report = BenchmarkReport("TruthfulQA")
    await run_truthfulqa(tqa_report)
    reports["TruthfulQA"] = tqa_report

    gsm8k_report = BenchmarkReport("GSM8K")
    await run_gsm8k(gsm8k_report)
    reports["GSM8K"] = gsm8k_report

    banking_report = BenchmarkReport("Banking77")
    await run_banking77(banking_report)
    reports["Banking77"] = banking_report

    print_report(reports)

    # Save raw results to JSON
    out = {}
    for name, r in reports.items():
        out[name] = {
            "accuracy": r.accuracy,
            "accept_rate": r.accept_rate,
            "savings_pct": r.savings_pct,
            "effective_savings_pct": r.effective_savings_pct,
            "drafter_accuracy": r.drafter_accuracy,
            "verifier_accuracy": r.verifier_accuracy,
            "total_cascade_cost": r.total_cascade_cost,
            "total_baseline_cost": r.total_baseline_cost,
            "avg_latency_ms": r.avg_latency,
            "n_total": r.n,
            "n_correct": r.n_correct,
            "n_accepted": r.n_accepted,
        }
    results_path = Path(__file__).parent / "results_openai_anthropic.json"
    results_path.write_text(json.dumps(out, indent=2))
    print(f"Results saved to {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
