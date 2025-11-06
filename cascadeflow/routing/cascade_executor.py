"""
Multi-Step Cascade Executor

This module executes domain-specific cascade pipelines with validation at each step.
Handles step execution, quality checking, fallback logic, and result aggregation.

Example:
    >>> from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    >>> from cascadeflow.routing.cascade_pipeline import get_code_strategy
    >>> from cascadeflow.routing.domain import Domain
    >>>
    >>> # Initialize with CODE strategy
    >>> executor = MultiStepCascadeExecutor(
    ...     strategies=[get_code_strategy()]
    ... )
    >>>
    >>> # Execute CODE pipeline
    >>> result = await executor.execute(
    ...     query="Write a quicksort function in Python",
    ...     domain=Domain.CODE
    ... )
    >>> print(f"Success: {result.success}")
    >>> print(f"Cost: ${result.total_cost:.4f}")
    >>> print(f"Steps: {len(result.steps_executed)}")
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional

from cascadeflow.routing.cascade_pipeline import (
    CascadeExecutionResult,
    CascadeStep,
    DomainCascadeStrategy,
    StepResult,
    StepStatus,
    ValidationMethod,
)
from cascadeflow.routing.domain import Domain

logger = logging.getLogger(__name__)


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_syntax(response: str, metadata: dict[str, Any]) -> tuple[bool, float, dict[str, Any]]:
    """
    Validate code syntax.

    Simple heuristic-based validation (production would use ast.parse, etc.)

    Args:
        response: Generated response
        metadata: Validation metadata

    Returns:
        Tuple of (passed, score, details)
    """
    details = {}

    # Check if response contains code
    has_code = any(marker in response for marker in ["def ", "function ", "class ", "```"])
    details["has_code"] = has_code

    if not has_code:
        return False, 0.3, details

    # Check for basic code structure
    score = 0.5

    # Has function definition
    if "def " in response or "function " in response:
        score += 0.2
        details["has_function"] = True

    # Has return statement
    if "return" in response:
        score += 0.1
        details["has_return"] = True

    # Has docstring or comments
    if '"""' in response or "#" in response or "//" in response:
        score += 0.1
        details["has_documentation"] = True

    # Not too short (likely incomplete)
    if len(response) > 100:
        score += 0.1
        details["adequate_length"] = True

    passed = score >= 0.7
    return passed, score, details


def validate_fact_check(
    response: str, metadata: dict[str, Any]
) -> tuple[bool, float, dict[str, Any]]:
    """
    Basic fact-checking validation for medical/legal domains.

    Production would use knowledge bases, retrieval, or specialized models.

    Args:
        response: Generated response
        metadata: Validation metadata

    Returns:
        Tuple of (passed, score, details)
    """
    details = {}

    score = 0.5  # Base score

    # Check for disclaimers (important for medical/legal)
    has_disclaimer = any(
        phrase in response.lower()
        for phrase in ["consult", "professional", "not medical advice", "not legal advice"]
    )
    details["has_disclaimer"] = has_disclaimer

    if has_disclaimer:
        score += 0.2

    # Check for hedging (good for uncertain domains)
    has_hedging = any(
        phrase in response.lower()
        for phrase in ["may", "might", "could", "possibly", "generally", "typically"]
    )
    details["has_hedging"] = has_hedging

    if has_hedging:
        score += 0.1

    # Check for specificity (has numbers, dates, references)
    has_specifics = any(char.isdigit() for char in response)
    details["has_specifics"] = has_specifics

    if has_specifics:
        score += 0.1

    # Adequate length (not too short)
    if len(response) > 200:
        score += 0.1
        details["adequate_length"] = True

    passed = score >= 0.75
    return passed, score, details


def validate_safety(response: str, metadata: dict[str, Any]) -> tuple[bool, float, dict[str, Any]]:
    """
    Safety and toxicity validation.

    Args:
        response: Generated response
        metadata: Validation metadata

    Returns:
        Tuple of (passed, score, details)
    """
    details = {}

    # Check for toxic keywords (simple keyword-based)
    toxic_keywords = ["kill", "harm", "dangerous", "illegal", "weapon"]
    toxic_found = [kw for kw in toxic_keywords if kw in response.lower()]
    details["toxic_keywords_found"] = toxic_found

    score = 1.0 - (len(toxic_found) * 0.2)  # Reduce score for toxic content

    # Check for safety disclaimers
    has_safety_disclaimer = any(
        phrase in response.lower()
        for phrase in ["caution", "warning", "consult professional", "seek help"]
    )
    details["has_safety_disclaimer"] = has_safety_disclaimer

    if has_safety_disclaimer and len(toxic_found) > 0:
        score += 0.1  # Bonus for adding disclaimers with potentially sensitive content

    passed = score >= 0.9 and len(toxic_found) == 0
    return passed, score, details


def validate_quality(response: str, metadata: dict[str, Any]) -> tuple[bool, float, dict[str, Any]]:
    """
    General quality validation.

    Args:
        response: Generated response
        metadata: Validation metadata

    Returns:
        Tuple of (passed, score, details)
    """
    details = {}

    score = 0.5  # Base score

    # Length check (not too short, not too long)
    length = len(response)
    details["length"] = length

    if 50 < length < 5000:
        score += 0.2
        details["good_length"] = True
    elif length < 50:
        details["too_short"] = True
    else:
        details["too_long"] = True

    # Check for completeness (no truncation)
    appears_complete = not response.endswith("...")
    details["appears_complete"] = appears_complete

    if appears_complete:
        score += 0.1

    # Check for coherence (basic heuristics)
    has_paragraphs = "\n" in response
    details["has_paragraphs"] = has_paragraphs

    if has_paragraphs:
        score += 0.1

    # Check for specific content (not too generic)
    word_count = len(response.split())
    unique_words = len(set(response.lower().split()))
    diversity_ratio = unique_words / word_count if word_count > 0 else 0
    details["diversity_ratio"] = round(diversity_ratio, 2)

    if diversity_ratio > 0.4:  # Good vocabulary diversity
        score += 0.1
        details["good_diversity"] = True

    passed = score >= 0.7
    return passed, score, details


def validate_full_quality(
    response: str, metadata: dict[str, Any]
) -> tuple[bool, float, dict[str, Any]]:
    """
    Comprehensive quality validation (combines multiple checks).

    Args:
        response: Generated response
        metadata: Validation metadata

    Returns:
        Tuple of (passed, score, details)
    """
    details = {}

    # Run multiple validations
    quality_passed, quality_score, quality_details = validate_quality(response, metadata)
    details["quality"] = quality_details

    safety_passed, safety_score, safety_details = validate_safety(response, metadata)
    details["safety"] = safety_details

    # Combined score (weighted)
    combined_score = (quality_score * 0.7) + (safety_score * 0.3)
    details["combined_score"] = combined_score

    passed = quality_passed and safety_passed and combined_score >= 0.85
    return passed, combined_score, details


# Validation function registry
VALIDATION_FUNCTIONS = {
    ValidationMethod.NONE: lambda r, m: (True, 1.0, {}),
    ValidationMethod.SYNTAX_CHECK: validate_syntax,
    ValidationMethod.FACT_CHECK: validate_fact_check,
    ValidationMethod.SAFETY_CHECK: validate_safety,
    ValidationMethod.QUALITY_CHECK: validate_quality,
    ValidationMethod.FULL_QUALITY: validate_full_quality,
}


# ============================================================================
# EXECUTOR
# ============================================================================


class MultiStepCascadeExecutor:
    """
    Executes multi-step cascade pipelines with validation.

    Handles:
    - Step-by-step execution
    - Validation at each step
    - Fallback to more capable models
    - Cost tracking
    - Result aggregation

    Attributes:
        strategies: Domain-specific strategies
        enable_fallback: Whether to use fallback steps
        max_retries: Maximum retries per step
        custom_validators: Custom validation functions
    """

    def __init__(
        self,
        strategies: Optional[list[DomainCascadeStrategy]] = None,
        enable_fallback: bool = True,
        max_retries: int = 2,
        custom_validators: Optional[dict[str, Callable]] = None,
    ):
        """
        Initialize executor.

        Args:
            strategies: List of domain strategies (uses built-in if None)
            enable_fallback: Whether to use fallback steps
            max_retries: Maximum retries per step
            custom_validators: Custom validation functions
        """
        self.strategies = strategies or []
        self.enable_fallback = enable_fallback
        self.max_retries = max_retries
        self.custom_validators = custom_validators or {}

        # Build strategy map
        self.strategy_map: dict[Domain, DomainCascadeStrategy] = {}
        for strategy in self.strategies:
            self.strategy_map[strategy.domain] = strategy

    def add_strategy(self, strategy: DomainCascadeStrategy):
        """Add a strategy for a domain."""
        self.strategy_map[strategy.domain] = strategy
        if strategy not in self.strategies:
            self.strategies.append(strategy)

    def get_strategy(self, domain: Domain) -> Optional[DomainCascadeStrategy]:
        """Get strategy for a domain."""
        return self.strategy_map.get(domain)

    async def execute(
        self, query: str, domain: Domain, user_id: Optional[str] = None, **kwargs
    ) -> CascadeExecutionResult:
        """
        Execute multi-step cascade for a domain.

        Args:
            query: User query
            domain: Domain to execute
            user_id: Optional user ID
            **kwargs: Additional execution parameters

        Returns:
            CascadeExecutionResult with complete execution details
        """
        strategy = self.get_strategy(domain)

        if not strategy:
            # No strategy for this domain - return error
            return CascadeExecutionResult(
                success=False,
                domain=domain,
                strategy_used="none",
                final_response="",
                steps_executed=[],
                total_cost=0.0,
                total_latency_ms=0.0,
                total_tokens=0,
                quality_score=0.0,
                fallback_used=False,
                metadata={"error": f"No strategy found for domain {domain}"},
            )

        if not strategy.enabled:
            # Strategy disabled
            return CascadeExecutionResult(
                success=False,
                domain=domain,
                strategy_used=strategy.description or str(domain),
                final_response="",
                steps_executed=[],
                total_cost=0.0,
                total_latency_ms=0.0,
                total_tokens=0,
                quality_score=0.0,
                fallback_used=False,
                metadata={"error": "Strategy disabled"},
            )

        logger.info(f"Executing {domain} strategy: {strategy.description}")

        # Execute pipeline
        steps_executed = []
        total_cost = 0.0
        total_latency_ms = 0.0
        total_tokens = 0
        final_response = ""
        final_quality_score = 0.0
        fallback_used = False

        # Execute primary steps (non-fallback)
        primary_steps = [s for s in strategy.steps if not s.fallback_only]

        for step in primary_steps:
            step_result = await self._execute_step(step, query, user_id, **kwargs)
            steps_executed.append(step_result)

            total_cost += step_result.cost
            total_latency_ms += step_result.latency_ms
            total_tokens += step_result.tokens_used

            if step_result.status == StepStatus.SUCCESS:
                # Step succeeded!
                final_response = step_result.response
                final_quality_score = step_result.quality_score
                break  # No need to execute fallback

        # If primary steps failed, execute fallback steps
        if not final_response and self.enable_fallback:
            logger.info("Primary steps failed, executing fallback steps")
            fallback_used = True

            fallback_steps = strategy.get_fallback_steps()

            for step in fallback_steps:
                step_result = await self._execute_step(step, query, user_id, **kwargs)
                steps_executed.append(step_result)

                total_cost += step_result.cost
                total_latency_ms += step_result.latency_ms
                total_tokens += step_result.tokens_used

                if step_result.status == StepStatus.SUCCESS:
                    final_response = step_result.response
                    final_quality_score = step_result.quality_score
                    break

        success = bool(final_response)

        return CascadeExecutionResult(
            success=success,
            domain=domain,
            strategy_used=strategy.description or str(domain),
            final_response=final_response,
            steps_executed=steps_executed,
            total_cost=total_cost,
            total_latency_ms=total_latency_ms,
            total_tokens=total_tokens,
            quality_score=final_quality_score,
            fallback_used=fallback_used,
            metadata={
                "query": query,
                "user_id": user_id,
                "steps_attempted": len(steps_executed),
                "steps_successful": len(
                    [s for s in steps_executed if s.status == StepStatus.SUCCESS]
                ),
            },
        )

    async def _execute_step(
        self, step: CascadeStep, query: str, user_id: Optional[str], **kwargs
    ) -> StepResult:
        """
        Execute a single cascade step.

        Args:
            step: Step to execute
            query: User query
            user_id: Optional user ID
            **kwargs: Additional parameters

        Returns:
            StepResult with execution details
        """
        logger.info(f"Executing step: {step.name} ({step.model})")

        start_time = time.time()

        try:
            # Simulate model call (in production, this would call actual provider)
            # For now, we'll simulate with a placeholder response
            response = await self._simulate_model_call(step, query)

            latency_ms = (time.time() - start_time) * 1000

            # Validate response
            validation_fn = VALIDATION_FUNCTIONS.get(step.validation)
            if not validation_fn:
                validation_fn = self.custom_validators.get(step.validation)

            if validation_fn:
                passed, score, details = validation_fn(response, step.metadata)
            else:
                # No validation function - assume pass
                passed = True
                score = 1.0
                details = {}

            # Check if passed quality threshold
            if passed and score >= step.quality_threshold:
                status = StepStatus.SUCCESS
            else:
                status = StepStatus.FAILED_QUALITY

            # Estimate cost (simplified - in production, use actual provider pricing)
            tokens_used = len(response.split()) * 2  # Rough estimate
            cost = self._estimate_cost(step.provider, step.model, tokens_used)

            return StepResult(
                step_name=step.name,
                status=status,
                response=response if status == StepStatus.SUCCESS else None,
                quality_score=score,
                cost=cost,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                validation_details=details,
                metadata={
                    "model": step.model,
                    "provider": step.provider,
                    "validation": step.validation,
                    "threshold": step.quality_threshold,
                },
            )

        except Exception as e:
            logger.error(f"Step {step.name} failed with error: {e}")

            latency_ms = (time.time() - start_time) * 1000

            return StepResult(
                step_name=step.name,
                status=StepStatus.FAILED_ERROR,
                error=str(e),
                latency_ms=latency_ms,
                metadata={"model": step.model, "provider": step.provider},
            )

    async def _simulate_model_call(self, step: CascadeStep, query: str) -> str:
        """
        Simulate model API call.

        In production, this would call the actual provider API.
        For testing, we generate placeholder responses.

        Args:
            step: Step configuration
            query: User query

        Returns:
            Simulated response
        """
        # Simulate API latency
        await asyncio.sleep(0.1)

        # Generate domain-specific placeholder response
        if "code" in query.lower() or "function" in query.lower():
            return """def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)"""

        elif "medical" in query.lower() or "diagnosis" in query.lower():
            return """Based on the symptoms described, this could indicate several conditions.
However, it's important to consult with a healthcare professional for an accurate diagnosis.
Common conditions with these symptoms include [conditions]. Please seek medical attention
if symptoms persist or worsen."""

        else:
            return f"""Here's a detailed response to your query: {query[:100]}...

This is a comprehensive answer that addresses the main points of your question.
It includes relevant information and context to help you understand the topic better.

Key points:
1. First important point
2. Second important point
3. Third important point

Would you like me to elaborate on any specific aspect?"""

    def _estimate_cost(self, provider: str, model: str, tokens: int) -> float:
        """
        Estimate cost for a model call.

        In production, this would use actual provider pricing.

        Args:
            provider: Provider name
            model: Model name
            tokens: Tokens used

        Returns:
            Estimated cost in USD
        """
        # Simplified cost estimation
        cost_per_1k_tokens = {
            "openai": {
                "gpt-4": 0.03,
                "gpt-4o": 0.0025,
                "gpt-4o-mini": 0.00015,
                "gpt-3.5-turbo": 0.0005,
            },
            "deepseek": {
                "deepseek-coder": 0.0014,
            },
            "groq": {
                "llama-3.1-70b-versatile": 0.0007,
                "llama-3.1-8b-instant": 0.0001,
            },
        }

        provider_costs = cost_per_1k_tokens.get(provider, {})
        cost_per_1k = provider_costs.get(model, 0.001)  # Default fallback

        return (tokens / 1000) * cost_per_1k
