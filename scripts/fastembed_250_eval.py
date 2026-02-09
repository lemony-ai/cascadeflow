#!/usr/bin/env python3
"""Comprehensive fastembed production evaluation (250 queries).

Calls cascadeflow (OpenAI-compatible) and a validator model (Claude).

Outputs:
  - /tmp/fastembed-250-eval-results.json
  - /tmp/fastembed-250-eval-report.md
\nThe script is intentionally self-contained and does not depend on cascadeflow
internals; it only needs HTTP access to the two /v1/chat/completions endpoints.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

import requests


CASCADEFLOW_URL_DEFAULT = "http://192.168.0.147:8084/v1/chat/completions"
VALIDATOR_URL_DEFAULT = "http://localhost:8087/v1/chat/completions"
VALIDATOR_MODEL_DEFAULT = "claude-opus-4-6"


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> tuple[dict[str, Any], float]:
    start = time.perf_counter()
    resp = requests.post(url, json=payload, timeout=timeout_s)
    latency_ms = (time.perf_counter() - start) * 1000.0
    resp.raise_for_status()
    return resp.json(), latency_ms


def _extract_text(response_json: dict[str, Any]) -> str:
    try:
        return response_json["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""


def _detect_accept_reject(assistant_text: str) -> Literal["accepted", "rejected", "unknown"]:
    text = assistant_text.lower()

    # Common explicit decision markers.
    if re.search(r"\b(reject|rejected|route to (?:strong|full)|hand off to|escalate)\b", text):
        return "rejected"
    if re.search(r"\b(accept|accepted|use fastembed|fastembed route|cheap model|draft ok)\b", text):
        return "accepted"

    # Heuristic: if the answer is substantive, assume accepted.
    if len(text.strip()) >= 40:
        return "accepted"

    return "unknown"


def _safe_json_loads(maybe_json: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(maybe_json)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


VALIDATOR_SYSTEM = (
    "You are a strict evaluator for a routing decision. "
    "You will be given a user query and the router's decision "
    "(accepted=fast route, rejected=slow/strong route). "
    "Return ONLY valid JSON with keys: decision_correct (0 or 1), "
    "expected_decision (accepted|rejected), rationale (string, <= 2 sentences)."
)


def _validator_expected_decision(query: str) -> Literal["accepted", "rejected"]:
    q = query.lower().strip()

    # Tool / delegation generally need stronger routing.
    if any(k in q for k in ["call a tool", "function call", "use the tool", "delegate", "sub-agent", "agent"]) :
        return "rejected"
    if re.search(r"\b(json schema|openapi|sql query|regex|proof|derive|complexity|optimiz)\b", q):
        return "rejected"

    # Very short but hard tends to need strong.
    if len(q.split()) <= 6 and re.search(r"\bwhy|prove|derive|counterexample|best\b", q):
        return "rejected"

    # Long queries: if they ask for deep reasoning, reject.
    if len(q) > 700 and re.search(r"\b(analyze|compare|trade-?offs|deep|step-?by-?step|proof)\b", q):
        return "rejected"

    return "accepted"


def _ask_validator(
    url: str,
    model: str,
    query: str,
    actual_decision: Literal["accepted", "rejected", "unknown"],
    timeout_s: float,
) -> tuple[dict[str, Any], float]:
    expected = _validator_expected_decision(query)

    user_payload = {
        "query": query,
        "router_decision": actual_decision,
        "note": "expected_decision is a ground-truth judgment for routing correctness",
    }

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": VALIDATOR_SYSTEM},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    }

    resp_json, latency_ms = _post_json(url, payload, timeout_s=timeout_s)
    text = _extract_text(resp_json)
    parsed = _safe_json_loads(text) or {
        "decision_correct": 0,
        "expected_decision": expected,
        "rationale": "Validator output was not JSON; counted as incorrect.",
    }

    # Enforce expected_decision consistency with our baseline if missing.
    if parsed.get("expected_decision") not in ("accepted", "rejected"):
        parsed["expected_decision"] = expected
    if parsed.get("decision_correct") not in (0, 1):
        parsed["decision_correct"] = 0
    if not isinstance(parsed.get("rationale"), str):
        parsed["rationale"] = ""

    # If validator says correct but expected mismatches our baseline, keep validator as-is.
    return parsed, latency_ms


@dataclass(frozen=True)
class QueryCase:
    id: str
    category: str
    messages: list[ChatMessage]


def _mk_messages(user_text: str, system_text: str | None = None) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})
    return messages


def _generate_cases(seed: int) -> list[QueryCase]:
    rnd = random.Random(seed)
    cases: list[QueryCase] = []

    # 1) Multi-turn conversations (42)
    multi_turn_starters = [
        "I’m planning a weekend trip. Ask me 3 questions first.",
        "Help me debug a Python error: TypeError on None. Ask clarifying questions.",
        "I want to start strength training. Ask about my goals and schedule.",
        "I need a study plan for learning linear algebra. Ask about my background.",
        "Help me write a polite email to reschedule a meeting. Ask for details.",
        "I’m choosing between two job offers. Ask what I value most.",
    ]
    for i in range(42):
        start = rnd.choice(multi_turn_starters)
        cases.append(
            QueryCase(
                id=f"multi_turn_{i:03d}",
                category="multi-turn",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": start},
                    {"role": "assistant", "content": "Sure—first, a few questions: 1) ... 2) ... 3) ..."},
                    {"role": "user", "content": "Answer the questions with reasonable assumptions and proceed."},
                ],
            )
        )

    # 2) Super long trivial (42)
    trivial_topics = [
        "Explain how to boil pasta safely.",
        "Summarize the water cycle in plain language.",
        "Write a friendly guide to basic email etiquette.",
        "Explain what a resume is and what to include.",
        "Describe how to clean a cast iron pan.",
        "Explain the difference between weather and climate.",
    ]
    for i in range(42):
        prompt = (
            rnd.choice(trivial_topics)
            + "\n\nWrite at least 600 words, with headings and bullet points. Keep it simple."
        )
        cases.append(QueryCase(id=f"long_trivial_{i:03d}", category="super-long-trivial", messages=_mk_messages(prompt)))

    # 3) Super long hard (42)
    hard_topics = [
        "Give a detailed argument comparing functional vs OOP design for a large codebase, including trade-offs, testing strategy, and team scaling.",
        "Analyze the pros/cons of different database indexing strategies for a high-write system, and propose a plan with metrics.",
        "Explain how gradient descent works, then derive the update rule for linear regression and discuss convergence issues.",
        "Design an incident response plan for a SaaS outage, including roles, comms, timelines, and postmortem process.",
        "Provide a step-by-step approach to threat modeling a web app with authentication and payments, including mitigations.",
    ]
    for i in range(42):
        prompt = rnd.choice(hard_topics) + "\n\nWrite 700-1000 words. Include a structured outline and concrete examples."
        cases.append(QueryCase(id=f"long_hard_{i:03d}", category="super-long-hard", messages=_mk_messages(prompt)))

    # 4) Super short hard (40)
    short_hard = [
        "Prove (sketch) that sqrt(2) is irrational.",
        "Why is time complexity of quicksort average O(n log n)?",
        "Give a counterexample to distributivity in matrices.",
        "Derive Bayes' theorem from conditional probability.",
        "Explain why HTTPS prevents MITM (briefly).",
        "What are the CAP theorem tradeoffs?",
    ]
    for i in range(40):
        cases.append(QueryCase(id=f"short_hard_{i:03d}", category="super-short-hard", messages=_mk_messages(rnd.choice(short_hard))))

    # 5) Super short trivial (40)
    short_trivial = [
        "What is the capital of France?",
        "Define photosynthesis.",
        "How many minutes in an hour?",
        "Translate 'hello' to Spanish.",
        "What does CPU stand for?",
        "Is water wet?",
    ]
    for i in range(40):
        cases.append(QueryCase(id=f"short_trivial_{i:03d}", category="super-short-trivial", messages=_mk_messages(rnd.choice(short_trivial))))

    # 6) Tool calls / function calling queries (22)
    tool_call_prompts = [
        "You have a function get_weather(city). Call it for 'San Francisco' and return JSON.",
        "Use function search_docs(query) to find 'rate limit' and summarize.",
        "Call create_ticket(title, severity) for a login outage. Return the tool args only.",
        "Extract entities from the text and output a JSON list with fields name,type.",
        "Given this schema, output a SQL query to compute daily active users.",
    ]
    for i in range(22):
        prompt = rnd.choice(tool_call_prompts)
        cases.append(QueryCase(id=f"tool_calls_{i:03d}", category="tool-calls", messages=_mk_messages(prompt)))

    # 7) Sub-agent patterns / delegation tasks (22)
    delegation_prompts = [
        "Delegate this task to a sub-agent: write a test plan for a payments refactor.",
        "Act as a manager: assign 3 sub-agents tasks to ship a feature; include responsibilities.",
        "Break down this project into sub-agents with parallel workstreams and risks.",
        "Create a sub-agent prompt to analyze logs and find root cause.",
    ]
    for i in range(22):
        prompt = rnd.choice(delegation_prompts)
        cases.append(QueryCase(id=f"sub_agents_{i:03d}", category="sub-agent-patterns", messages=_mk_messages(prompt)))

    if len(cases) != 250:
        raise RuntimeError(f"Expected 250 cases, got {len(cases)}")

    return cases


def _make_report(results: list[dict[str, Any]], started_at: str, ended_at: str) -> str:
    latencies = [r["cascadeflow"]["latency_ms"] for r in results if r.get("cascadeflow", {}).get("latency_ms") is not None]
    accept = sum(1 for r in results if r["decision"] == "accepted")
    reject = sum(1 for r in results if r["decision"] == "rejected")
    unknown = sum(1 for r in results if r["decision"] == "unknown")
    score = sum(int(r.get("validator", {}).get("decision_correct", 0)) for r in results)

    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = statistics.quantiles(latencies, n=20)[-1] if len(latencies) >= 20 else (max(latencies) if latencies else 0.0)
    avg = statistics.mean(latencies) if latencies else 0.0

    lines: list[str] = []
    lines.append("# fastembed production evaluation (250 queries)")
    lines.append("")
    lines.append(f"- Started: {started_at}")
    lines.append(f"- Ended: {ended_at}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total queries | {len(results)} |")
    lines.append(f"| Accepted | {accept} |")
    lines.append(f"| Rejected | {reject} |")
    lines.append(f"| Unknown | {unknown} |")
    lines.append(f"| Validator score (correct decisions) | {score} |")
    lines.append(f"| Accuracy | {score/len(results):.3f} |")
    lines.append(f"| Avg latency (ms) | {avg:.1f} |")
    lines.append(f"| P50 latency (ms) | {p50:.1f} |")
    lines.append(f"| P95 latency (ms) | {p95:.1f} |")
    lines.append("")

    lines.append("## By category")
    lines.append("")
    cats = sorted({r["category"] for r in results})
    lines.append("| Category | N | Accuracy | Avg latency (ms) | Accepted | Rejected | Unknown |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for c in cats:
        subset = [r for r in results if r["category"] == c]
        n = len(subset)
        s = sum(int(r.get("validator", {}).get("decision_correct", 0)) for r in subset)
        lats = [r["cascadeflow"]["latency_ms"] for r in subset]
        a = sum(1 for r in subset if r["decision"] == "accepted")
        rj = sum(1 for r in subset if r["decision"] == "rejected")
        u = sum(1 for r in subset if r["decision"] == "unknown")
        lines.append(f"| {c} | {n} | {s/n:.3f} | {statistics.mean(lats):.1f} | {a} | {rj} | {u} |")

    lines.append("")
    lines.append("## FastEmbed analysis (heuristic)")
    lines.append("")
    lines.append(
        "This run captures whether the router tends to accept/reject across query types and "
        "how that aligns with an external validator decision. Use the per-query rationales "
        "to identify false accepts (hard queries routed fast) and false rejects (easy queries routed slow)."
    )
    lines.append("")
    lines.append("### Opportunities")
    lines.append("")
    lines.append("- Quality detection potential: focus on false-accept cases; extract features (length, domain, tool-intent, ambiguity).")
    lines.append("- Complexity pre-routing: add a cheap complexity heuristic for very-short-hard and tool-intent queries.")
    lines.append("- Self-learning: use validator labels to train/threshold domain routing rules.")
    lines.append("- Semantic caching: cache accepted responses for near-duplicate short-trivial prompts.")
    lines.append("- Domain expansion: review highest-latency rejects that validator marks as accept.")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cascadeflow-url", default=CASCADEFLOW_URL_DEFAULT)
    parser.add_argument("--validator-url", default=VALIDATOR_URL_DEFAULT)
    parser.add_argument("--validator-model", default=VALIDATOR_MODEL_DEFAULT)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--out-json", default="/tmp/fastembed-250-eval-results.json")
    parser.add_argument("--out-md", default="/tmp/fastembed-250-eval-report.md")
    args = parser.parse_args()

    started_at = _utc_now_iso()
    cases = _generate_cases(args.seed)

    results: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        payload = {
            "model": "cascadeflow",
            "temperature": 0,
            "messages": case.messages,
        }

        cascadeflow_resp: dict[str, Any]
        cascadeflow_latency: float
        error: str | None = None
        try:
            cascadeflow_resp, cascadeflow_latency = _post_json(args.cascadeflow_url, payload, timeout_s=args.timeout_s)
        except Exception as e:  # noqa: BLE001
            cascadeflow_resp, cascadeflow_latency = {}, 0.0
            error = f"cascadeflow_call_failed: {e}"

        assistant_text = _extract_text(cascadeflow_resp)
        decision = _detect_accept_reject(assistant_text)

        validator_resp: dict[str, Any]
        validator_latency: float
        try:
            validator_resp, validator_latency = _ask_validator(
                args.validator_url,
                args.validator_model,
                query=case.messages[-1]["content"],
                actual_decision=decision,
                timeout_s=args.timeout_s,
            )
        except Exception as e:  # noqa: BLE001
            validator_resp, validator_latency = {
                "decision_correct": 0,
                "expected_decision": _validator_expected_decision(case.messages[-1]["content"]),
                "rationale": f"validator_call_failed: {e}",
            }, 0.0

        results.append(
            {
                "id": case.id,
                "category": case.category,
                "messages": case.messages,
                "decision": decision,
                "cascadeflow": {
                    "latency_ms": cascadeflow_latency,
                    "response": cascadeflow_resp,
                    "assistant_text": assistant_text,
                    "error": error,
                },
                "validator": {
                    "latency_ms": validator_latency,
                    **validator_resp,
                },
            }
        )

        if idx % 10 == 0:
            print(f"Progress: {idx}/250")

    ended_at = _utc_now_iso()

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "started_at": started_at,
                "ended_at": ended_at,
                "cascadeflow_url": args.cascadeflow_url,
                "validator_url": args.validator_url,
                "validator_model": args.validator_model,
                "seed": args.seed,
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    report_md = _make_report(results, started_at=started_at, ended_at=ended_at)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(report_md)

    # Print summary table.
    latencies = [r["cascadeflow"]["latency_ms"] for r in results]
    score = sum(int(r.get("validator", {}).get("decision_correct", 0)) for r in results)
    accept = sum(1 for r in results if r["decision"] == "accepted")
    reject = sum(1 for r in results if r["decision"] == "rejected")
    unknown = sum(1 for r in results if r["decision"] == "unknown")
    print("\nSummary")
    print("-------")
    print(f"Total: 250")
    print(f"Accepted: {accept}  Rejected: {reject}  Unknown: {unknown}")
    print(f"Score: {score}/250  Accuracy: {score/250:.3f}")
    print(f"Avg latency (ms): {statistics.mean(latencies):.1f}  P50: {statistics.median(latencies):.1f}  Max: {max(latencies):.1f}")
    print(f"Wrote: {args.out_json}")
    print(f"Wrote: {args.out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
