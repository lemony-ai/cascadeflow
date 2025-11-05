"""
cascadeflow Tool Streaming Module - Complete Implementation
===========================================================

Real-time streaming for tool-calling cascades with progressive JSON parsing,
validation, and optional execution.

Features:
- Progressive tool call display (show args as they arrive)
- Tool validation (check correctness before execution)
- Optional auto-execution with feedback
- Multi-turn conversation support
- Integration with ToolQualityValidator
- Error handling and recovery
🆕 Input token counting for accurate cost tracking

Architecture:
    ToolStreamManager wraps WholeResponseCascade to provide real-time
    tool call streaming with complete validation and execution support.

Usage:
    from cascadeflow.streaming import ToolStreamManager, ToolStreamEventType

    manager = ToolStreamManager(cascade)

    async for event in manager.stream(query, tools=tools):
        match event.type:
            case ToolStreamEventType.TOOL_CALL_START:
                print(f"\\n[{event.tool_call['name']}]")
            case ToolStreamEventType.TOOL_CALL_DELTA:
                print(event.delta, end='')
            case ToolStreamEventType.TOOL_RESULT:
                print(f"\\n→ {event.tool_result}")
            case ToolStreamEventType.TEXT_CHUNK:
                print(event.content, end='')
"""

import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from .utils import (
    JSONParseState,
    ProgressiveJSONParser,
    ToolCallValidator,
)

logger = logging.getLogger(__name__)


# ============================================================================
# EVENT TYPES AND DATA STRUCTURES
# ============================================================================


class ToolStreamEventType(Enum):
    """Tool-specific streaming event types."""

    ROUTING = "routing"
    TOOL_CALL_START = "tool_call_start"  # Tool call detected
    TOOL_CALL_DELTA = "tool_call_delta"  # Arguments streaming
    TOOL_CALL_COMPLETE = "tool_call_complete"  # Tool call formed
    TOOL_EXECUTING = "tool_executing"  # Executing tool
    TOOL_RESULT = "tool_result"  # Execution result
    TOOL_ERROR = "tool_error"  # Tool error
    TEXT_CHUNK = "text_chunk"  # Text response
    DRAFT_DECISION = "draft_decision"  # Quality decision
    SWITCH = "switch"  # Cascading
    COMPLETE = "complete"  # All done
    ERROR = "error"  # System error


@dataclass
class ToolStreamEvent:
    """
    Tool streaming event with structured data.

    Contains tool-specific fields for progressive display and validation.
    """

    type: ToolStreamEventType
    content: str = ""

    # Tool-specific fields
    tool_call: Optional[dict[str, Any]] = None  # Full or partial tool call
    delta: Optional[str] = None  # Progressive argument delta
    tool_result: Optional[Any] = None  # Execution result
    error: Optional[str] = None  # Error message

    # Standard metadata
    data: Optional[dict[str, Any]] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


# ============================================================================
# TOOL STREAMING MANAGER
# ============================================================================


class ToolStreamManager:
    """
    Manages streaming for tool-calling cascades.

    Key Features:
    1. Progressive JSON parsing - show tool calls as they arrive
    2. Tool validation - check correctness before execution
    3. Optional auto-execution - execute and continue
    4. Multi-turn support - handle conversation history
    5. Quality validation - use ToolQualityValidator
    6. 🆕 Input token counting - accurate cost tracking

    Example:
        manager = ToolStreamManager(cascade)

        async for event in manager.stream(query, tools=tools):
            if event.type == ToolStreamEventType.TOOL_CALL_START:
                print(f"[Calling: {event.tool_call['name']}]")
    """

    def __init__(self, cascade, tool_executor: Optional[Callable] = None, verbose: bool = False):
        """
        Initialize tool stream manager.

        Args:
            cascade: WholeResponseCascade instance
            tool_executor: Optional function to execute tools
                          Signature: async def execute(tool_call, tools) -> result
            verbose: Enable verbose logging
        """
        self.cascade = cascade
        self.tool_executor = tool_executor
        self.verbose = verbose

        if verbose:
            logger.setLevel(logging.INFO)

        self.json_parser = ProgressiveJSONParser()
        self.validator = ToolCallValidator()

        # 🆕 Initialize CostCalculator from telemetry module
        try:
            from ..telemetry.cost_calculator import CostCalculator

            self.cost_calculator = CostCalculator(
                drafter=cascade.drafter, verifier=cascade.verifier, verbose=verbose
            )
            self._has_cost_calculator = True
            if verbose:
                logger.info("✅ CostCalculator initialized from telemetry module")
        except ImportError:
            self.cost_calculator = None
            self._has_cost_calculator = False
            if verbose:
                logger.warning("⚠️ CostCalculator not available - using fallback")

        logger.info("ToolStreamManager initialized")

    def _estimate_tokens_from_text(self, text: str) -> int:
        """
        Estimate token count from text.

        Uses standard approximation: 1 token ≈ 0.75 words (1.3 tokens per word)

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        word_count = len(text.split())
        return max(1, int(word_count * 1.3))

    def _calculate_costs(
        self,
        draft_content: str,
        verifier_content: Optional[str],
        draft_accepted: bool,
        query_text: str = "",
        tool_calls: Optional[list[dict]] = None,
    ) -> dict[str, float]:
        """
        Calculate costs using CostCalculator with input token counting.

        🆕 FIXED: Now includes query_text for input token counting!

        Args:
            draft_content: Draft model's output
            verifier_content: Verifier model's output (if cascaded)
            draft_accepted: Whether draft was accepted
            query_text: Original query text for input token counting (NEW!)
            tool_calls: Tool calls made (for metadata)

        Returns:
            Dict with draft_cost, verifier_cost, total_cost, cost_saved, tokens
        """
        if self._has_cost_calculator and self.cost_calculator:
            try:
                # Estimate OUTPUT tokens only
                draft_output_tokens = self._estimate_tokens_from_text(draft_content)

                # Add tool call token overhead (JSON structure)
                if tool_calls:
                    for tc in tool_calls:
                        # Rough estimate: name + args as JSON
                        tc_str = json.dumps(tc)
                        draft_output_tokens += self._estimate_tokens_from_text(tc_str)

                verifier_output_tokens = (
                    self._estimate_tokens_from_text(verifier_content) if verifier_content else 0
                )

                # 🆕 Estimate INPUT tokens from query
                query_input_tokens = self._estimate_tokens_from_text(query_text)

                # Use CostCalculator WITH input tokens
                breakdown = self.cost_calculator.calculate_from_tokens(
                    draft_output_tokens=draft_output_tokens,
                    verifier_output_tokens=verifier_output_tokens,
                    draft_accepted=draft_accepted,
                    query_input_tokens=query_input_tokens,  # 🆕 NEW!
                )

                if self.verbose:
                    logger.info(
                        f"💰 CostCalculator (tools): "
                        f"input={query_input_tokens}, "
                        f"draft_output={draft_output_tokens}, "
                        f"verifier_output={verifier_output_tokens}, "
                        f"tool_calls={len(tool_calls) if tool_calls else 0}, "
                        f"draft=${breakdown.draft_cost:.6f}, "
                        f"verifier=${breakdown.verifier_cost:.6f}, "
                        f"total=${breakdown.total_cost:.6f}"
                    )

                return {
                    "draft_cost": breakdown.draft_cost,
                    "verifier_cost": breakdown.verifier_cost,
                    "total_cost": breakdown.total_cost,
                    "cost_saved": breakdown.cost_saved,
                    "draft_tokens": breakdown.draft_tokens,
                    "verifier_tokens": breakdown.verifier_tokens,
                    "total_tokens": breakdown.total_tokens,
                }

            except Exception as e:
                logger.warning(f"CostCalculator failed: {e}, using fallback")

        # Fallback: Manual calculation (includes input tokens)
        query_input_tokens = self._estimate_tokens_from_text(query_text)
        draft_output_tokens = self._estimate_tokens_from_text(draft_content)

        # Add tool call overhead
        if tool_calls:
            for tc in tool_calls:
                tc_str = json.dumps(tc)
                draft_output_tokens += self._estimate_tokens_from_text(tc_str)

        draft_total_tokens = query_input_tokens + draft_output_tokens
        draft_cost = (draft_total_tokens / 1000) * self.cascade.drafter.cost

        if draft_accepted:
            # Draft accepted - only paid for draft
            verifier_would_be_tokens = query_input_tokens + draft_output_tokens
            verifier_cost_avoided = (verifier_would_be_tokens / 1000) * self.cascade.verifier.cost
            cost_saved = verifier_cost_avoided - draft_cost

            return {
                "draft_cost": draft_cost,
                "verifier_cost": 0.0,
                "total_cost": draft_cost,
                "cost_saved": cost_saved,
                "draft_tokens": draft_total_tokens,
                "verifier_tokens": 0,
                "total_tokens": draft_total_tokens,
            }
        else:
            # Draft rejected - paid for both
            verifier_output_tokens = self._estimate_tokens_from_text(verifier_content)
            verifier_total_tokens = query_input_tokens + verifier_output_tokens
            verifier_cost = (verifier_total_tokens / 1000) * self.cascade.verifier.cost
            total_cost = draft_cost + verifier_cost
            cost_saved = -draft_cost

            return {
                "draft_cost": draft_cost,
                "verifier_cost": verifier_cost,
                "total_cost": total_cost,
                "cost_saved": cost_saved,
                "draft_tokens": draft_total_tokens,
                "verifier_tokens": verifier_total_tokens,
                "total_tokens": draft_total_tokens + verifier_total_tokens,
            }

    async def stream(
        self,
        query: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        tool_choice: Optional[dict[str, Any]] = None,
        execute_tools: bool = False,
        max_turns: int = 1,
        complexity: Optional[str] = None,
        routing_strategy: str = "cascade",
        **kwargs,
    ) -> AsyncIterator[ToolStreamEvent]:
        """
        Stream tool-calling cascade execution with input token counting.

        🆕 FIXED: Now properly includes input tokens in all cost calculations!

        Args:
            query: User query
            tools: Tool definitions (required)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            tool_choice: Tool selection strategy (auto/required/specific)
            execute_tools: If True, auto-execute tools and continue
            max_turns: Maximum conversation turns (for multi-turn)
            complexity: Query complexity (for quality validation)
            routing_strategy: "cascade" or "direct"
            **kwargs: Additional provider parameters

        Yields:
            ToolStreamEvent objects with tool-specific data

        Event Flow:
            1. ROUTING - Strategy chosen
            2. TOOL_CALL_START - Tool call begins
            3. TOOL_CALL_DELTA (multiple) - Arguments stream in
            4. TOOL_CALL_COMPLETE - Tool call ready
            5. [TOOL_EXECUTING] - If execute_tools=True
            6. [TOOL_RESULT] - Execution result
            7. TEXT_CHUNK (multiple) - Final response
            8. COMPLETE - Done
        """
        if not tools:
            raise ValueError("tools parameter is required for tool streaming")

        try:
            logger.info(f"Starting tool streaming for query: {query[:50]}...")

            # Emit routing event
            yield ToolStreamEvent(
                type=ToolStreamEventType.ROUTING,
                data={
                    "strategy": routing_strategy,
                    "complexity": complexity or "unknown",
                    "tools_available": len(tools),
                    "execute_tools": execute_tools,
                },
            )

            # 🔧 FIX: Build messages list from query
            messages = [{"role": "user", "content": query}]

            # Add system prompt if provided in kwargs
            if "system_prompt" in kwargs:
                messages.insert(0, {"role": "system", "content": kwargs.pop("system_prompt")})

            # 🔧 FIX: Clean kwargs to prevent parameter duplication
            # Remove tools, tool_choice, and internal parameters
            provider_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                not in {
                    "tools",  # Will be passed explicitly
                    "tool_choice",  # Will be passed explicitly
                    "routing_strategy",  # Internal parameter
                    "is_direct_route",  # Internal parameter
                    "complexity",  # Internal parameter
                    "execute_tools",  # Internal parameter
                    "max_turns",  # Internal parameter
                }
            }

            # ℹ️ DO NOT add tools/tool_choice to provider_kwargs
            # They will be passed explicitly to avoid duplicate keyword arguments

            # ================================================================
            # STAGE 1: Stream Draft with Tool Calls
            # ================================================================

            overall_start_time = time.time()
            draft_start_time = time.time()

            draft_provider = self.cascade.providers[self.cascade.drafter.provider]
            draft_model = self.cascade.drafter

            draft_chunks = []
            draft_content = ""
            tool_calls_found = []
            current_tool_call = None
            json_buffer = ""

            logger.info(f"Streaming from draft model: {draft_model.name}")

            # Check if provider supports tool calling
            if hasattr(draft_provider, "complete_with_tools"):
                # Use tool-specific method
                if hasattr(draft_provider, "stream_with_tools"):
                    # Streaming with tools
                    logger.info("Using stream_with_tools for progressive tool streaming")

                    # 🔧 FIX: Pass messages instead of model/prompt
                    async for chunk in draft_provider.stream_with_tools(
                        messages=messages,  # ✅ FIXED
                        tools=tools,  # ← Explicit
                        max_tokens=max_tokens,
                        temperature=temperature,
                        tool_choice=tool_choice,  # ← Explicit
                        **provider_kwargs,  # ← Does NOT contain tools/tool_choice
                    ):
                        # Process chunk for tool calls
                        async for event in self._process_tool_chunk(
                            chunk, tools, current_tool_call, json_buffer
                        ):
                            yield event

                            # Track tool calls
                            if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                                tool_calls_found.append(event.tool_call)
                                current_tool_call = None
                                json_buffer = ""
                            elif event.type == ToolStreamEventType.TOOL_CALL_DELTA:
                                json_buffer += event.delta

                        draft_chunks.append(chunk)
                        draft_content += str(chunk)

                else:
                    # Non-streaming with tools
                    logger.info("Using complete_with_tools (non-streaming)")

                    # 🔧 FIX: Pass messages instead of model/prompt
                    response = await draft_provider.complete_with_tools(
                        messages=messages,  # ✅ FIXED
                        tools=tools,  # ← Explicit
                        max_tokens=max_tokens,
                        temperature=temperature,
                        tool_choice=tool_choice,  # ← Explicit
                        **provider_kwargs,  # ← Does NOT contain tools/tool_choice
                    )

                    # Extract tool calls from response
                    if hasattr(response, "tool_calls") and response.tool_calls:
                        for tool_call in response.tool_calls:
                            tool_calls_found.append(tool_call)

                            # Emit events
                            yield ToolStreamEvent(
                                type=ToolStreamEventType.TOOL_CALL_START,
                                tool_call={"name": tool_call.get("name", "unknown")},
                                data={"model": draft_model.name},
                            )

                            yield ToolStreamEvent(
                                type=ToolStreamEventType.TOOL_CALL_COMPLETE,
                                tool_call=tool_call,
                                data={"model": draft_model.name},
                            )

                    draft_content = response.content or ""

                    # Emit text if present
                    if draft_content:
                        yield ToolStreamEvent(
                            type=ToolStreamEventType.TEXT_CHUNK,
                            content=draft_content,
                            data={"model": draft_model.name, "phase": "draft"},
                        )

            else:
                # Provider doesn't support tools - error
                error_msg = f"Provider {draft_model.provider} doesn't support tool calling"
                logger.error(error_msg)
                yield ToolStreamEvent(type=ToolStreamEventType.ERROR, error=error_msg)
                return

            draft_latency_ms = (time.time() - draft_start_time) * 1000

            logger.info(
                f"Draft complete: {len(tool_calls_found)} tool calls, "
                f"{len(draft_content)} chars, {draft_latency_ms:.0f}ms"
            )

            # ================================================================
            # STAGE 2: Validate Tool Calls
            # ================================================================

            if tool_calls_found:
                logger.info("Validating tool calls...")
                quality_check_start = time.time()

                # Validate each tool call
                all_valid = True
                validation_reasons = []

                for tool_call in tool_calls_found:
                    is_valid, reason = self.validator.validate_tool_call(tool_call, tools)

                    if not is_valid:
                        all_valid = False
                        validation_reasons.append(f"{tool_call.get('name')}: {reason}")
                        logger.warning(f"Tool call validation failed: {reason}")

                # Use ToolQualityValidator if available
                tool_quality_passed = True
                quality_score = 0.95 if all_valid else 0.3

                if (
                    hasattr(self.cascade, "tool_quality_validator")
                    and self.cascade.tool_quality_validator is not None
                ):
                    validation_result = self.cascade.tool_quality_validator.validate(
                        tool_calls=tool_calls_found, available_tools=tools
                    )
                    # Handle both dict and float return types
                    if isinstance(validation_result, dict):
                        tool_quality_passed = validation_result.get("passed", False)
                        quality_score = validation_result.get("score", 0.5)
                    else:
                        # validation_result is a float score
                        quality_score = float(validation_result)
                        tool_quality_passed = quality_score >= 0.75

                quality_check_ms = (time.time() - quality_check_start) * 1000
                draft_accepted = all_valid and tool_quality_passed

                # Emit draft decision
                yield ToolStreamEvent(
                    type=ToolStreamEventType.DRAFT_DECISION,
                    data={
                        "accepted": draft_accepted,
                        "score": quality_score,
                        "tool_calls_valid": all_valid,
                        "tool_calls_count": len(tool_calls_found),
                        "draft_model": draft_model.name,
                        "verifier_model": self.cascade.verifier.name,
                        "reason": "quality_passed" if draft_accepted else "quality_failed",
                        "validation_reasons": validation_reasons,
                    },
                )

                logger.info(
                    f"Tool validation: {'PASSED' if draft_accepted else 'FAILED'} "
                    f"(score: {quality_score:.2f}, overhead: {quality_check_ms:.1f}ms)"
                )

            else:
                # No tool calls found
                draft_accepted = False
                quality_score = 0.0
                quality_check_ms = 0

                logger.warning("No tool calls found in draft response")

            # ================================================================
            # STAGE 3: Execute Tools (if enabled and accepted)
            # ================================================================

            tool_results = []

            if execute_tools and draft_accepted and tool_calls_found:
                logger.info(f"Executing {len(tool_calls_found)} tool(s)...")

                for tool_call in tool_calls_found:
                    # Emit executing event
                    yield ToolStreamEvent(
                        type=ToolStreamEventType.TOOL_EXECUTING,
                        tool_call=tool_call,
                        data={"tool_name": tool_call.get("name")},
                    )

                    try:
                        # Execute tool
                        if self.tool_executor:
                            result = await self.tool_executor(tool_call, tools)
                        else:
                            result = await self._default_tool_executor(tool_call, tools)

                        tool_results.append(
                            {"tool_call": tool_call, "result": result, "success": True}
                        )

                        # Emit result event
                        yield ToolStreamEvent(
                            type=ToolStreamEventType.TOOL_RESULT,
                            tool_call=tool_call,
                            tool_result=result,
                            data={"success": True},
                        )

                        logger.info(f"Tool {tool_call.get('name')} executed successfully")

                    except Exception as e:
                        error_msg = str(e)
                        tool_results.append(
                            {"tool_call": tool_call, "error": error_msg, "success": False}
                        )

                        # Emit error event
                        yield ToolStreamEvent(
                            type=ToolStreamEventType.TOOL_ERROR,
                            tool_call=tool_call,
                            error=error_msg,
                            data={"tool_name": tool_call.get("name")},
                        )

                        logger.error(f"Tool execution failed: {error_msg}")

            # ================================================================
            # STAGE 4: Handle Result or Cascade
            # ================================================================

            if draft_accepted and not execute_tools:
                # Draft accepted, return tool calls
                total_latency_ms = (time.time() - overall_start_time) * 1000

                # 🆕 Calculate costs WITH query_text
                costs = self._calculate_costs(
                    draft_content=draft_content,
                    verifier_content=None,
                    draft_accepted=True,
                    query_text=query,  # 🆕 NEW!
                    tool_calls=tool_calls_found,
                )

                result_data = {
                    "content": draft_content,
                    "tool_calls": tool_calls_found,
                    "tool_results": tool_results,
                    "model_used": draft_model.name,
                    "draft_accepted": True,
                    "cascaded": False,
                    "latency_ms": total_latency_ms,
                    "quality_score": quality_score,
                    "total_cost": costs["total_cost"],  # 🆕
                    "draft_cost": costs["draft_cost"],  # 🆕
                    "verifier_cost": costs["verifier_cost"],  # 🆕
                    "cost_saved": costs["cost_saved"],  # 🆕
                    "draft_tokens": costs["draft_tokens"],  # 🆕 Includes input!
                    "verifier_tokens": costs["verifier_tokens"],  # 🆕
                    "total_tokens": costs["total_tokens"],  # 🆕
                }

                yield ToolStreamEvent(
                    type=ToolStreamEventType.COMPLETE, data={"result": result_data}
                )

                logger.info(
                    f"Tool streaming complete: {total_latency_ms:.0f}ms, "
                    f"cost=${costs['total_cost']:.6f}"
                )
                return

            elif draft_accepted and execute_tools:
                # Tools executed, could continue for multi-turn
                # For now, just return results
                total_latency_ms = (time.time() - overall_start_time) * 1000

                # 🆕 Calculate costs WITH query_text
                costs = self._calculate_costs(
                    draft_content=draft_content,
                    verifier_content=None,
                    draft_accepted=True,
                    query_text=query,  # 🆕 NEW!
                    tool_calls=tool_calls_found,
                )

                result_data = {
                    "content": draft_content,
                    "tool_calls": tool_calls_found,
                    "tool_results": tool_results,
                    "model_used": draft_model.name,
                    "draft_accepted": True,
                    "tools_executed": True,
                    "latency_ms": total_latency_ms,
                    "total_cost": costs["total_cost"],  # 🆕
                    "draft_cost": costs["draft_cost"],  # 🆕
                    "verifier_cost": costs["verifier_cost"],  # 🆕
                    "cost_saved": costs["cost_saved"],  # 🆕
                    "draft_tokens": costs["draft_tokens"],  # 🆕 Includes input!
                    "verifier_tokens": costs["verifier_tokens"],  # 🆕
                    "total_tokens": costs["total_tokens"],  # 🆕
                }

                yield ToolStreamEvent(
                    type=ToolStreamEventType.COMPLETE, data={"result": result_data}
                )

                logger.info(
                    f"Tool execution complete: {total_latency_ms:.0f}ms, "
                    f"cost=${costs['total_cost']:.6f}"
                )
                return

            else:
                # Draft rejected, cascade to verifier
                logger.info("Draft rejected, cascading to verifier...")

                yield ToolStreamEvent(
                    type=ToolStreamEventType.SWITCH,
                    content=f"⤴ Cascading to {self.cascade.verifier.name}",
                    data={
                        "from_model": draft_model.name,
                        "to_model": self.cascade.verifier.name,
                        "reason": "Tool call quality insufficient",
                    },
                )

                # ============================================================
                # STAGE 5: Verifier with Tools
                # ============================================================

                verifier_start_time = time.time()
                verifier_provider = self.cascade.providers[self.cascade.verifier.provider]
                verifier_model = self.cascade.verifier

                verifier_tool_calls = []
                verifier_content = ""

                if hasattr(verifier_provider, "complete_with_tools"):
                    if hasattr(verifier_provider, "stream_with_tools"):
                        # Streaming verifier
                        logger.info("Verifier: Using stream_with_tools")

                        # 🔧 FIX: Pass messages instead of model/prompt
                        async for chunk in verifier_provider.stream_with_tools(
                            messages=messages,  # ✅ FIXED
                            tools=tools,  # ← Explicit
                            max_tokens=max_tokens,
                            temperature=temperature,
                            tool_choice=tool_choice,  # ← Explicit
                            **provider_kwargs,  # ← Clean kwargs
                        ):
                            # Process chunk
                            async for event in self._process_tool_chunk(chunk, tools, None, ""):
                                # Update event to show it's from verifier
                                event.data["model"] = verifier_model.name
                                event.data["phase"] = "verifier"
                                yield event

                                if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                                    verifier_tool_calls.append(event.tool_call)

                            verifier_content += str(chunk)

                    else:
                        # Non-streaming verifier
                        logger.info("Verifier: Using complete_with_tools (non-streaming)")

                        # 🔧 FIX: Pass messages instead of model/prompt
                        response = await verifier_provider.complete_with_tools(
                            messages=messages,  # ✅ FIXED
                            tools=tools,  # ← Explicit
                            max_tokens=max_tokens,
                            temperature=temperature,
                            tool_choice=tool_choice,  # ← Explicit
                            **provider_kwargs,  # ← Clean kwargs
                        )

                        if hasattr(response, "tool_calls") and response.tool_calls:
                            for tool_call in response.tool_calls:
                                verifier_tool_calls.append(tool_call)

                                yield ToolStreamEvent(
                                    type=ToolStreamEventType.TOOL_CALL_COMPLETE,
                                    tool_call=tool_call,
                                    data={"model": verifier_model.name, "phase": "verifier"},
                                )

                        verifier_content = response.content or ""

                        if verifier_content:
                            yield ToolStreamEvent(
                                type=ToolStreamEventType.TEXT_CHUNK,
                                content=verifier_content,
                                data={"model": verifier_model.name, "phase": "verifier"},
                            )

                verifier_latency_ms = (time.time() - verifier_start_time) * 1000
                total_latency_ms = (time.time() - overall_start_time) * 1000

                # Execute verifier tools if needed
                if execute_tools and verifier_tool_calls:
                    logger.info(f"Executing {len(verifier_tool_calls)} verifier tool(s)...")

                    for tool_call in verifier_tool_calls:
                        yield ToolStreamEvent(
                            type=ToolStreamEventType.TOOL_EXECUTING, tool_call=tool_call
                        )

                        try:
                            if self.tool_executor:
                                result = await self.tool_executor(tool_call, tools)
                            else:
                                result = await self._default_tool_executor(tool_call, tools)

                            tool_results.append(
                                {"tool_call": tool_call, "result": result, "success": True}
                            )

                            yield ToolStreamEvent(
                                type=ToolStreamEventType.TOOL_RESULT,
                                tool_call=tool_call,
                                tool_result=result,
                            )

                        except Exception as e:
                            tool_results.append(
                                {"tool_call": tool_call, "error": str(e), "success": False}
                            )

                            yield ToolStreamEvent(
                                type=ToolStreamEventType.TOOL_ERROR,
                                tool_call=tool_call,
                                error=str(e),
                            )

                # 🆕 Calculate costs WITH query_text for cascaded path
                costs = self._calculate_costs(
                    draft_content=draft_content,
                    verifier_content=verifier_content,
                    draft_accepted=False,
                    query_text=query,  # 🆕 NEW!
                    tool_calls=verifier_tool_calls or tool_calls_found,
                )

                # Final result
                result_data = {
                    "content": verifier_content,
                    "tool_calls": verifier_tool_calls,
                    "tool_results": tool_results,
                    "model_used": verifier_model.name,
                    "draft_accepted": False,
                    "cascaded": True,
                    "latency_ms": total_latency_ms,
                    "draft_latency_ms": draft_latency_ms,
                    "verifier_latency_ms": verifier_latency_ms,
                    "total_cost": costs["total_cost"],  # 🆕 Includes both models + input!
                    "draft_cost": costs["draft_cost"],  # 🆕
                    "verifier_cost": costs["verifier_cost"],  # 🆕
                    "cost_saved": costs["cost_saved"],  # 🆕 (negative)
                    "draft_tokens": costs["draft_tokens"],  # 🆕 Includes input!
                    "verifier_tokens": costs["verifier_tokens"],  # 🆕 Includes input!
                    "total_tokens": costs["total_tokens"],  # 🆕
                }

                yield ToolStreamEvent(
                    type=ToolStreamEventType.COMPLETE, data={"result": result_data}
                )

                logger.info(
                    f"Cascaded tool streaming complete: {total_latency_ms:.0f}ms, "
                    f"cost=${costs['total_cost']:.6f}"
                )

        except Exception as e:
            logger.error(f"Tool streaming error: {e}", exc_info=True)
            yield ToolStreamEvent(
                type=ToolStreamEventType.ERROR, error=str(e), data={"error_type": type(e).__name__}
            )

    async def _process_tool_chunk(
        self,
        chunk: Any,
        tools: list[dict[str, Any]],
        current_tool_call: Optional[dict],
        json_buffer: str,
    ) -> AsyncIterator[ToolStreamEvent]:
        """
        Process a chunk for tool calls with progressive JSON parsing.

        Emits events as tool calls are detected and parsed.
        """
        # Check if chunk contains tool call data
        # (Provider-specific logic would go here)

        # For now, simple implementation
        chunk_str = str(chunk)

        # Check for tool call markers
        if '"name":' in chunk_str or '"function":' in chunk_str:
            # Potential tool call
            if current_tool_call is None:
                # New tool call starting
                yield ToolStreamEvent(
                    type=ToolStreamEventType.TOOL_CALL_START, data={"detected": True}
                )
                current_tool_call = {}

            # Add to buffer and try to parse
            json_buffer += chunk_str

            result = self.json_parser.parse(json_buffer)

            if result.state == JSONParseState.PARTIAL and result.data:
                # Emit delta
                yield ToolStreamEvent(
                    type=ToolStreamEventType.TOOL_CALL_DELTA, delta=chunk_str, tool_call=result.data
                )

            elif result.state == JSONParseState.COMPLETE:
                # Complete tool call
                yield ToolStreamEvent(
                    type=ToolStreamEventType.TOOL_CALL_COMPLETE, tool_call=result.data
                )

        else:
            # Regular text
            if chunk_str.strip():
                yield ToolStreamEvent(type=ToolStreamEventType.TEXT_CHUNK, content=chunk_str)

    async def _default_tool_executor(
        self, tool_call: dict[str, Any], tools: list[dict[str, Any]]
    ) -> Any:
        """
        Default tool executor (returns mock result).

        Override by passing custom tool_executor to __init__.
        """
        tool_name = tool_call.get("name", "unknown")
        arguments = tool_call.get("arguments", {})

        logger.info(f"Mock execution of tool: {tool_name} with args: {arguments}")

        return {"status": "success", "message": f"Mock result for {tool_name}", "data": arguments}


__all__ = [
    "ToolStreamEventType",
    "ToolStreamEvent",
    "ToolStreamManager",
]
