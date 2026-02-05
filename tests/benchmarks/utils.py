"""Benchmark utilities for model selection and provider resolution."""

from __future__ import annotations

import os
from typing import Optional

from .benchmark_config import DRAFTER_MODELS, VERIFIER_MODELS


def get_env_model(env_name: str, default: str) -> str:
    """Return model name overridden by environment variable if set."""
    return os.getenv(env_name, default)


def resolve_model_provider(model: str, fallback: str = "openai") -> str:
    """Infer provider from model name."""
    model_lower = model.lower()
    if "claude" in model_lower or model_lower.startswith("anthropic/"):
        return "anthropic"
    if model_lower.startswith("gpt") or model_lower.startswith("openai/"):
        return "openai"
    if model_lower.startswith("gemini") or model_lower.startswith("google/"):
        return "google"
    if model_lower.startswith("groq/"):
        return "groq"
    if model_lower.startswith("together/"):
        return "together"
    if model_lower.startswith("huggingface/"):
        return "huggingface"
    if model_lower.startswith("deepseek/"):
        return "deepseek"
    return fallback


def resolve_model_cost(model: str, fallback: float) -> float:
    """Resolve model cost per 1k tokens from benchmark config tiers."""
    for tier in DRAFTER_MODELS.values():
        if tier.name == model:
            return tier.cost_per_1k
    for tier in VERIFIER_MODELS.values():
        if tier.name == model:
            return tier.cost_per_1k

    model_lower = model.lower()
    if "claude-haiku" in model_lower:
        return 0.003
    if "claude-opus" in model_lower:
        return 0.045
    if "claude-sonnet" in model_lower:
        return 0.003

    return fallback


def resolve_model_pair(
    default_drafter: str,
    default_verifier: str,
    env_drafter: str = "DRAFTER_MODEL",
    env_verifier: str = "VERIFIER_MODEL",
) -> tuple[str, str]:
    """Return drafter/verifier names with env overrides applied."""
    return (
        get_env_model(env_drafter, default_drafter),
        get_env_model(env_verifier, default_verifier),
    )
