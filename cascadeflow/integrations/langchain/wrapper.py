"""CascadeFlow LangChain wrapper - transparent wrapper for LangChain chat models.

Preserves all LangChain model functionality while adding intelligent
cascade logic for cost optimization.

Example:
    >>> from langchain_openai import ChatOpenAI
    >>> from cascadeflow.langchain import CascadeFlow
    >>>
    >>> drafter = ChatOpenAI(model='gpt-4o-mini')
    >>> verifier = ChatOpenAI(model='gpt-4o')
    >>>
    >>> cascade = CascadeFlow(
    ...     drafter=drafter,
    ...     verifier=verifier,
    ...     quality_threshold=0.7
    ... )
    >>>
    >>> result = await cascade.ainvoke("What is TypeScript?")
"""

import asyncio
import inspect
import time
from typing import Any, AsyncIterator, Iterator, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from cascadeflow.routing.tool_risk import get_tool_risk_routing

from .types import CascadeResult
from .utils import calculate_quality, create_cost_metadata, extract_tool_calls


class CascadeFlow(BaseChatModel):
    """CascadeFlow - Transparent wrapper for LangChain chat models.

    Implements the speculative execution pattern with automatic quality-based
    routing between a fast drafter model and an accurate verifier model.

    Attributes:
        drafter: The drafter model (cheap, fast) - tries first
        verifier: The verifier model (expensive, accurate) - used when quality is insufficient
        quality_threshold: Quality threshold for accepting drafter responses (0-1)
        enable_cost_tracking: Enable automatic cost tracking
        cost_tracking_provider: Cost tracking provider ('langsmith' or 'cascadeflow')
        quality_validator: Custom quality validator function
        enable_pre_router: Enable pre-routing based on query complexity
        pre_router: Custom PreRouter instance
        cascade_complexities: Complexity levels that should use cascade
    """

    drafter: BaseChatModel
    verifier: BaseChatModel
    quality_threshold: float = 0.7
    enable_cost_tracking: bool = True
    # Default to local pricing for best DX (works without LangSmith).
    # Use "langsmith" if you want server-side cost computation in LangSmith UI.
    cost_tracking_provider: str = "cascadeflow"
    quality_validator: Optional[Any] = None
    enable_pre_router: bool = True
    pre_router: Optional[Any] = None
    cascade_complexities: list[str] = ["trivial", "simple", "moderate"]

    # Private state
    _last_cascade_result: Optional[CascadeResult] = None
    _bind_kwargs: dict[str, Any] = {}
    _bound_tool_defs: Optional[list[dict[str, Any]]] = None

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        drafter: BaseChatModel,
        verifier: BaseChatModel,
        quality_threshold: float = 0.7,
        enable_cost_tracking: bool = True,
        cost_tracking_provider: str = "cascadeflow",
        quality_validator: Optional[Any] = None,
        enable_pre_router: bool = True,
        pre_router: Optional[Any] = None,
        cascade_complexities: Optional[list[str]] = None,
        **kwargs: Any,
    ):
        """Initialize CascadeFlow wrapper.

        Args:
            drafter: The drafter model (cheap, fast)
            verifier: The verifier model (expensive, accurate)
            quality_threshold: Quality threshold for accepting drafter responses (0-1)
            enable_cost_tracking: Enable automatic cost tracking
            cost_tracking_provider: 'langsmith' (server-side) or 'cascadeflow' (local)
            quality_validator: Custom quality validator function
            enable_pre_router: Enable pre-routing based on query complexity
            pre_router: Custom PreRouter instance
            cascade_complexities: Complexity levels that should use cascade
            **kwargs: Additional arguments passed to BaseChatModel
        """
        # Initialize parent class
        super().__init__(
            drafter=drafter,
            verifier=verifier,
            quality_threshold=quality_threshold,
            enable_cost_tracking=enable_cost_tracking,
            cost_tracking_provider=cost_tracking_provider,
            quality_validator=quality_validator,
            enable_pre_router=enable_pre_router,
            pre_router=pre_router,
            cascade_complexities=cascade_complexities or ["trivial", "simple", "moderate"],
            **kwargs,
        )

        self._last_cascade_result = None
        self._bind_kwargs = {}
        self._bound_tool_defs = None

        # Initialize PreRouter if enabled
        if self.enable_pre_router and not self.pre_router:
            from .routers.pre_router import PreRouter

            self.pre_router = PreRouter({"cascade_complexities": self.cascade_complexities})

    @property
    def _llm_type(self) -> str:
        """Return LLM type identifier."""
        return "cascadeflow"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Core cascade generation logic.

        Implements the speculative execution pattern:
        1. Check PreRouter (if enabled) to determine routing strategy
        2. Execute drafter (cheap, fast model)
        3. Validate quality of drafter response
        4. If quality insufficient, execute verifier (expensive, accurate model)
        5. Track costs and metadata

        Args:
            messages: Input messages
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional arguments

        Returns:
            ChatResult with final response and metadata
        """
        start_time = time.time()

        # Merge bind kwargs with call kwargs
        merged_kwargs = {**self._bind_kwargs, **kwargs}
        if stop:
            merged_kwargs["stop"] = stop

        # Extract callbacks before filtering (need to pass them explicitly to nested models)
        callbacks = merged_kwargs.get("callbacks", [])

        existing_tags = merged_kwargs.get("tags", []) or []
        base_tags = existing_tags + ["cascadeflow"] if existing_tags else ["cascadeflow"]
        existing_metadata = merged_kwargs.get("metadata", {}) or {}
        base_metadata = {
            **existing_metadata,
            "cascadeflow": {**existing_metadata.get("cascadeflow", {}), "integration": "langchain"},
        }

        # Filter out callback-related keys that LangChain propagates automatically
        # Passing these explicitly to nested models would create duplicate parameter errors
        # NOTE: We keep 'tags' in safe_kwargs and merge with our tags for reliable LangSmith tracking
        safe_kwargs = {
            k: v
            for k, v in merged_kwargs.items()
            if k not in ("callbacks", "run_manager", "run_id", "stop")
        }

        # STEP 0: PreRouter - Check if we should bypass cascade
        use_cascade = True
        routing_decision = None

        if self.enable_pre_router and self.pre_router:
            # Extract query text from messages
            query_text = "\n".join(
                [msg.content if isinstance(msg.content, str) else "" for msg in messages]
            )

            # Route based on complexity
            routing_decision = self._route_query_sync(query_text)
            from .routers.base import RoutingStrategy

            use_cascade = (
                routing_decision is None
                or routing_decision.get("strategy") == RoutingStrategy.CASCADE
            )

            # If direct routing, skip drafter and go straight to verifier
            if routing_decision is not None and not use_cascade:
                # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
                verifier_tags = base_tags + [
                    "cascadeflow:direct",
                    "cascadeflow:verifier",
                    "verifier",
                ]
                verifier_llm_result = self.verifier.generate(
                    [messages],
                    stop=stop,
                    callbacks=callbacks,
                    **{
                        **safe_kwargs,
                        "tags": verifier_tags,
                        "metadata": {
                            **base_metadata,
                            "cascadeflow": {
                                **base_metadata["cascadeflow"],
                                "decision": "direct",
                                "role": "verifier",
                            },
                        },
                    },
                )

                # Convert LLMResult to ChatResult (generate returns LLMResult with nested generations)
                verifier_result = ChatResult(
                    generations=verifier_llm_result.generations[0],
                    llm_output=verifier_llm_result.llm_output,
                )

                latency_ms = (time.time() - start_time) * 1000
                verifier_model_name = (
                    getattr(self.verifier, "model_name", None)
                    or getattr(self.verifier, "model", None)
                    or self.verifier._llm_type
                )

                # Store cascade result (direct to verifier)
                self._last_cascade_result = CascadeResult(
                    content=verifier_result.generations[0].text,
                    model_used="verifier",
                    accepted=False,
                    drafter_quality=0.0,  # No drafter used (pre-router bypass)
                    drafter_cost=0.0,
                    verifier_cost=0.0,
                    total_cost=0.0,
                    savings_percentage=0.0,
                    latency_ms=latency_ms,
                )

                # Inject metadata if cost tracking enabled
                if self.enable_cost_tracking:
                    try:
                        metadata = {
                            "cascade_decision": "direct",
                            "model_used": "verifier",
                            "routing_reason": routing_decision["reason"],
                            "complexity": routing_decision.get("metadata", {}).get("complexity"),
                            "drafter_quality": 0.0,  # No drafter used (pre-router bypass)
                        }

                        if not verifier_result.llm_output:
                            verifier_result.llm_output = {}
                        verifier_result.llm_output["cascade"] = metadata

                        # Also inject into generation metadata
                        if verifier_result.generations:
                            gen = verifier_result.generations[0]
                            if hasattr(gen, "message") and gen.message:
                                if not hasattr(gen.message, "response_metadata"):
                                    gen.message.response_metadata = {}
                                gen.message.response_metadata["cascade"] = metadata
                    except Exception as e:
                        print(f"Warning: Failed to inject cascade metadata: {e}")

                return verifier_result

        # STEP 1: Execute drafter (cheap, fast model)
        # Merge existing tags from config with drafter tag for reliable LangSmith tracking
        drafter_tags = base_tags + ["cascadeflow:drafter", "drafter"]
        drafter_llm_result = self.drafter.generate(
            [messages],
            stop=stop,
            callbacks=callbacks,
            **{
                **safe_kwargs,
                "tags": drafter_tags,
                "metadata": {
                    **base_metadata,
                    "cascadeflow": {
                        **base_metadata["cascadeflow"],
                        "decision": "draft",
                        "role": "drafter",
                    },
                },
            },
        )

        # Convert LLMResult to ChatResult
        drafter_result = ChatResult(
            generations=drafter_llm_result.generations[0], llm_output=drafter_llm_result.llm_output
        )

        # Calculate drafter quality
        quality_func = self.quality_validator or calculate_quality
        drafter_tool_calls = extract_tool_calls(drafter_result)
        invoked_tool_names = self._extract_tool_call_names(drafter_tool_calls)

        tool_risk = None
        force_verifier_for_tool_risk = False
        if invoked_tool_names:
            invoked_defs = [self._get_tool_def_for_name(n) for n in invoked_tool_names]
            tool_risk = self._sanitize_tool_risk(get_tool_risk_routing(invoked_defs))
            force_verifier_for_tool_risk = bool(tool_risk.get("use_verifier"))

        drafter_quality = quality_func(drafter_result)

        # STEP 2: Check quality threshold.
        # Avoid `a and b`/`a or b` returning non-bools (e.g., lists) for mypy correctness.
        if invoked_tool_names:
            accepted = not force_verifier_for_tool_risk
        else:
            accepted = drafter_quality >= self.quality_threshold

        if accepted:
            # Quality is sufficient - use drafter response
            final_result = drafter_result
            verifier_result = None
        else:
            # Quality insufficient - execute verifier (expensive, accurate model)
            # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
            reason = "tool_risk" if force_verifier_for_tool_risk else "quality"
            verifier_tags = base_tags + [
                "cascadeflow:verifier",
                "verifier",
                "cascadeflow:escalated",
                f"cascadeflow:reason={reason}",
            ]
            if tool_risk and tool_risk.get("max_risk_name"):
                verifier_tags.append(f"cascadeflow:toolrisk={tool_risk['max_risk_name']}")
            verifier_llm_result = self.verifier.generate(
                [messages],
                stop=stop,
                callbacks=callbacks,
                **{
                    **safe_kwargs,
                    "tags": verifier_tags,
                    "metadata": {
                        **base_metadata,
                        "cascadeflow": {
                            **base_metadata["cascadeflow"],
                            "decision": "verify",
                            "role": "verifier",
                            "reason": reason,
                            "tool_risk": tool_risk,
                        },
                    },
                },
            )
            # Convert LLMResult to ChatResult
            verifier_result = ChatResult(
                generations=verifier_llm_result.generations[0],
                llm_output=verifier_llm_result.llm_output,
            )
            final_result = verifier_result

        # STEP 3: Calculate costs and metadata
        latency_ms = (time.time() - start_time) * 1000
        drafter_model_name = (
            getattr(self.drafter, "model_name", None)
            or getattr(self.drafter, "model", None)
            or self.drafter._llm_type
        )
        verifier_model_name = (
            getattr(self.verifier, "model_name", None)
            or getattr(self.verifier, "model", None)
            or self.verifier._llm_type
        )

        cost_metadata = create_cost_metadata(
            drafter_result,
            verifier_result,
            drafter_model_name,
            verifier_model_name,
            accepted,
            drafter_quality,
            self.cost_tracking_provider,
        )

        cascade_decision = (
            ("tool_call" if accepted else "tool_risk")
            if invoked_tool_names
            else ("accepted" if accepted else "quality")
        )

        # Store cascade result
        self._last_cascade_result = CascadeResult(
            content=final_result.generations[0].text,
            model_used="drafter" if accepted else "verifier",
            drafter_quality=drafter_quality,
            accepted=accepted,
            drafter_cost=cost_metadata["drafter_cost"],
            verifier_cost=cost_metadata["verifier_cost"],
            total_cost=cost_metadata["total_cost"],
            savings_percentage=cost_metadata["savings_percentage"],
            latency_ms=latency_ms,
        )

        # STEP 4: Inject cost metadata into llmOutput (if enabled)
        # LangSmith will automatically capture this metadata in traces
        if self.enable_cost_tracking:
            try:
                # Inject into llmOutput
                if not final_result.llm_output:
                    final_result.llm_output = {}
                final_result.llm_output["cascade"] = {
                    **cost_metadata,
                    "cascade_decision": cascade_decision,
                    "invoked_tools": invoked_tool_names or None,
                    "tool_risk": tool_risk,
                }

                # Also inject into message's response_metadata
                if final_result.generations:
                    gen = final_result.generations[0]
                    if hasattr(gen, "message") and gen.message:
                        if not hasattr(gen.message, "response_metadata"):
                            gen.message.response_metadata = {}
                        gen.message.response_metadata["cascade"] = final_result.llm_output[
                            "cascade"
                        ]
            except Exception as e:
                print(f"Warning: Failed to inject cascade metadata: {e}")

        return final_result

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async version of cascade generation logic.

        Args:
            messages: Input messages
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional arguments

        Returns:
            ChatResult with final response and metadata
        """
        start_time = time.time()

        # Merge bind kwargs with call kwargs
        merged_kwargs = {**self._bind_kwargs, **kwargs}
        if stop:
            merged_kwargs["stop"] = stop

        # Extract callbacks before filtering (need to pass them explicitly to nested models)
        callbacks = merged_kwargs.get("callbacks", [])

        existing_tags = merged_kwargs.get("tags", []) or []
        base_tags = existing_tags + ["cascadeflow"] if existing_tags else ["cascadeflow"]
        existing_metadata = merged_kwargs.get("metadata", {}) or {}
        base_metadata = {
            **existing_metadata,
            "cascadeflow": {**existing_metadata.get("cascadeflow", {}), "integration": "langchain"},
        }

        # Filter out callback-related keys that LangChain propagates automatically
        # Passing these explicitly to nested models would create duplicate parameter errors
        # NOTE: We keep 'tags' in safe_kwargs and merge with our tags for reliable LangSmith tracking
        safe_kwargs = {
            k: v
            for k, v in merged_kwargs.items()
            if k not in ("callbacks", "run_manager", "run_id", "stop")
        }

        # STEP 0: PreRouter - Check if we should bypass cascade
        use_cascade = True
        routing_decision = None

        if self.enable_pre_router and self.pre_router:
            # Extract query text from messages
            query_text = "\n".join(
                [msg.content if isinstance(msg.content, str) else "" for msg in messages]
            )

            # Route based on complexity
            routing_decision = await self.pre_router.route(query_text)
            from .routers.base import RoutingStrategy

            use_cascade = routing_decision["strategy"] == RoutingStrategy.CASCADE

            # If direct routing, skip drafter and go straight to verifier
            if not use_cascade:
                # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
                verifier_tags = base_tags + [
                    "cascadeflow:direct",
                    "cascadeflow:verifier",
                    "verifier",
                ]
                verifier_llm_result = await self.verifier.agenerate(
                    [messages],
                    stop=stop,
                    callbacks=callbacks,
                    **{
                        **safe_kwargs,
                        "tags": verifier_tags,
                        "metadata": {
                            **base_metadata,
                            "cascadeflow": {
                                **base_metadata["cascadeflow"],
                                "decision": "direct",
                                "role": "verifier",
                            },
                        },
                    },
                )

                # Convert LLMResult to ChatResult (agenerate returns LLMResult with nested generations)
                verifier_result = ChatResult(
                    generations=verifier_llm_result.generations[0],
                    llm_output=verifier_llm_result.llm_output,
                )

                latency_ms = (time.time() - start_time) * 1000
                verifier_model_name = (
                    getattr(self.verifier, "model_name", None)
                    or getattr(self.verifier, "model", None)
                    or self.verifier._llm_type
                )

                # Store cascade result (direct to verifier)
                self._last_cascade_result = CascadeResult(
                    content=verifier_result.generations[0].text,
                    model_used="verifier",
                    accepted=False,
                    drafter_quality=0.0,  # No drafter used (pre-router bypass)
                    drafter_cost=0.0,
                    verifier_cost=0.0,
                    total_cost=0.0,
                    savings_percentage=0.0,
                    latency_ms=latency_ms,
                )

                # Inject metadata if cost tracking enabled
                if self.enable_cost_tracking:
                    try:
                        metadata = {
                            "cascade_decision": "direct",
                            "model_used": "verifier",
                            "routing_reason": routing_decision["reason"],
                            "complexity": routing_decision.get("metadata", {}).get("complexity"),
                            "drafter_quality": 0.0,  # No drafter used (pre-router bypass)
                        }

                        if not verifier_result.llm_output:
                            verifier_result.llm_output = {}
                        verifier_result.llm_output["cascade"] = metadata

                        # Also inject into generation metadata
                        if verifier_result.generations:
                            gen = verifier_result.generations[0]
                            if hasattr(gen, "message") and gen.message:
                                if not hasattr(gen.message, "response_metadata"):
                                    gen.message.response_metadata = {}
                                gen.message.response_metadata["cascade"] = metadata
                    except Exception as e:
                        print(f"Warning: Failed to inject cascade metadata: {e}")

                return verifier_result

        # STEP 1: Execute drafter (cheap, fast model)
        # Merge existing tags from config with drafter tag for reliable LangSmith tracking
        drafter_tags = base_tags + ["cascadeflow:drafter", "drafter"]
        drafter_llm_result = await self.drafter.agenerate(
            [messages],
            stop=stop,
            callbacks=callbacks,
            **{
                **safe_kwargs,
                "tags": drafter_tags,
                "metadata": {
                    **base_metadata,
                    "cascadeflow": {
                        **base_metadata["cascadeflow"],
                        "decision": "draft",
                        "role": "drafter",
                    },
                },
            },
        )

        # Convert LLMResult to ChatResult
        drafter_result = ChatResult(
            generations=drafter_llm_result.generations[0], llm_output=drafter_llm_result.llm_output
        )

        # Calculate drafter quality
        quality_func = self.quality_validator or calculate_quality
        drafter_tool_calls = extract_tool_calls(drafter_result)
        invoked_tool_names = self._extract_tool_call_names(drafter_tool_calls)

        tool_risk = None
        force_verifier_for_tool_risk = False
        if invoked_tool_names:
            invoked_defs = [self._get_tool_def_for_name(n) for n in invoked_tool_names]
            tool_risk = self._sanitize_tool_risk(get_tool_risk_routing(invoked_defs))
            force_verifier_for_tool_risk = bool(tool_risk.get("use_verifier"))

        drafter_quality = quality_func(drafter_result)

        # STEP 2: Check quality threshold.
        if invoked_tool_names:
            accepted = not force_verifier_for_tool_risk
        else:
            accepted = drafter_quality >= self.quality_threshold

        if accepted:
            # Quality is sufficient - use drafter response
            final_result = drafter_result
            verifier_result = None
        else:
            # Quality insufficient - execute verifier (expensive, accurate model)
            # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
            reason = "tool_risk" if force_verifier_for_tool_risk else "quality"
            verifier_tags = base_tags + [
                "cascadeflow:verifier",
                "verifier",
                "cascadeflow:escalated",
                f"cascadeflow:reason={reason}",
            ]
            if tool_risk and tool_risk.get("max_risk_name"):
                verifier_tags.append(f"cascadeflow:toolrisk={tool_risk['max_risk_name']}")
            verifier_llm_result = await self.verifier.agenerate(
                [messages],
                stop=stop,
                callbacks=callbacks,
                **{
                    **safe_kwargs,
                    "tags": verifier_tags,
                    "metadata": {
                        **base_metadata,
                        "cascadeflow": {
                            **base_metadata["cascadeflow"],
                            "decision": "verify",
                            "role": "verifier",
                            "reason": reason,
                            "tool_risk": tool_risk,
                        },
                    },
                },
            )
            # Convert LLMResult to ChatResult
            verifier_result = ChatResult(
                generations=verifier_llm_result.generations[0],
                llm_output=verifier_llm_result.llm_output,
            )
            final_result = verifier_result

        # STEP 3: Calculate costs and metadata
        latency_ms = (time.time() - start_time) * 1000
        drafter_model_name = (
            getattr(self.drafter, "model_name", None)
            or getattr(self.drafter, "model", None)
            or self.drafter._llm_type
        )
        verifier_model_name = (
            getattr(self.verifier, "model_name", None)
            or getattr(self.verifier, "model", None)
            or self.verifier._llm_type
        )

        cost_metadata = create_cost_metadata(
            drafter_result,
            verifier_result,
            drafter_model_name,
            verifier_model_name,
            accepted,
            drafter_quality,
            self.cost_tracking_provider,
        )

        cascade_decision = (
            ("tool_call" if accepted else "tool_risk")
            if invoked_tool_names
            else ("accepted" if accepted else "quality")
        )

        # Store cascade result
        self._last_cascade_result = CascadeResult(
            content=final_result.generations[0].text,
            model_used="drafter" if accepted else "verifier",
            drafter_quality=drafter_quality,
            accepted=accepted,
            drafter_cost=cost_metadata["drafter_cost"],
            verifier_cost=cost_metadata["verifier_cost"],
            total_cost=cost_metadata["total_cost"],
            savings_percentage=cost_metadata["savings_percentage"],
            latency_ms=latency_ms,
        )

        # STEP 4: Inject cost metadata
        if self.enable_cost_tracking:
            try:
                if not final_result.llm_output:
                    final_result.llm_output = {}
                final_result.llm_output["cascade"] = {
                    **cost_metadata,
                    "cascade_decision": cascade_decision,
                    "invoked_tools": invoked_tool_names or None,
                    "tool_risk": tool_risk,
                }

                # Also inject into message's response_metadata
                if final_result.generations:
                    gen = final_result.generations[0]
                    if hasattr(gen, "message") and gen.message:
                        if not hasattr(gen.message, "response_metadata"):
                            gen.message.response_metadata = {}
                        gen.message.response_metadata["cascade"] = final_result.llm_output[
                            "cascade"
                        ]
            except Exception as e:
                print(f"Warning: Failed to inject cascade metadata: {e}")

        return final_result

    def get_last_cascade_result(self) -> Optional[CascadeResult]:
        """Get the last cascade execution result.

        Returns:
            CascadeResult with metadata from the last invocation, or None
        """
        return self._last_cascade_result

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream responses with optimistic drafter execution.

        Uses the proven cascade streaming pattern:
        1. Stream drafter optimistically (user sees real-time output)
        2. Collect chunks and check quality after completion
        3. If quality insufficient: show switch message + stream verifier

        Args:
            messages: Input messages
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional arguments

        Yields:
            ChatGenerationChunk instances with streaming content
        """
        start_time = time.time()

        # Merge bind kwargs with call kwargs
        merged_kwargs = {**self._bind_kwargs, **kwargs}
        if stop:
            merged_kwargs["stop"] = stop
        base_tags = (merged_kwargs.get("tags") or []) + ["cascadeflow"]
        base_metadata = {
            **(merged_kwargs.get("metadata") or {}),
            "cascadeflow": {
                **(
                    merged_kwargs.get("metadata", {}).get("cascadeflow", {})
                    if isinstance(merged_kwargs.get("metadata"), dict)
                    else {}
                ),
                "integration": "langchain",
                "streaming": True,
            },
        }
        emit_switch_message = bool(base_metadata.get("cascadeflow_emit_switch_message"))

        # STEP 0: PreRouter - Check if we should bypass cascade
        use_cascade = True
        routing_decision = None

        if self.enable_pre_router and self.pre_router:
            # Extract query text from messages
            query_text = "\n".join(
                [msg.content if isinstance(msg.content, str) else "" for msg in messages]
            )

            # Route based on complexity (sync call for sync streaming)
            routing_decision = self._route_query_sync(query_text)
            from .routers.base import RoutingStrategy

            use_cascade = (
                routing_decision is None
                or routing_decision.get("strategy") == RoutingStrategy.CASCADE
            )

            # If direct routing, stream verifier only
            if routing_decision is not None and not use_cascade:
                for chunk in self.verifier.stream(
                    messages,
                    **{
                        **merged_kwargs,
                        "tags": base_tags
                        + ["cascadeflow:direct", "cascadeflow:verifier", "verifier"],
                        "metadata": {
                            **base_metadata,
                            "cascadeflow": {
                                **base_metadata["cascadeflow"],
                                "decision": "direct",
                                "role": "verifier",
                            },
                        },
                    },
                ):
                    yield ChatGenerationChunk(
                        message=chunk, text=chunk.content if isinstance(chunk.content, str) else ""
                    )
                return

        tools_bound = bool(self._bound_tool_defs)
        drafter_chunks: list[AIMessageChunk] = []
        drafter_content = ""

        for chunk in self.drafter.stream(
            messages,
            **{
                **merged_kwargs,
                "tags": base_tags + ["cascadeflow:drafter", "drafter"],
                "metadata": {
                    **base_metadata,
                    "cascadeflow": {
                        **base_metadata["cascadeflow"],
                        "decision": "draft",
                        "role": "drafter",
                    },
                },
            },
        ):
            chunk_text = chunk.content if isinstance(chunk.content, str) else ""
            drafter_content += chunk_text
            drafter_chunks.append(chunk)
            if not tools_bound:
                yield ChatGenerationChunk(message=chunk, text=chunk_text)

        # STEP 2: Quality check after drafter completes
        combined_chunk = None
        for c in drafter_chunks:
            combined_chunk = c if combined_chunk is None else combined_chunk + c

        combined_message = (
            AIMessage(
                content=(
                    combined_chunk.content
                    if combined_chunk and isinstance(combined_chunk.content, str)
                    else drafter_content
                ),
                additional_kwargs=(
                    getattr(combined_chunk, "additional_kwargs", {}) if combined_chunk else {}
                ),
                tool_calls=getattr(combined_chunk, "tool_calls", None) if combined_chunk else None,
                invalid_tool_calls=(
                    getattr(combined_chunk, "invalid_tool_calls", None) if combined_chunk else None
                ),
                response_metadata=(
                    getattr(combined_chunk, "response_metadata", {}) if combined_chunk else {}
                ),
            )
            if combined_chunk
            else AIMessage(content=drafter_content)
        )
        drafter_result = ChatResult(
            generations=[ChatGeneration(text=drafter_content, message=combined_message)],
            llm_output={},
        )

        quality_func = self.quality_validator or calculate_quality
        drafter_tool_calls = extract_tool_calls(drafter_result)
        invoked_tool_names = self._extract_tool_call_names(drafter_tool_calls)
        tool_risk = None
        force_verifier_for_tool_risk = False
        if invoked_tool_names:
            invoked_defs = [self._get_tool_def_for_name(n) for n in invoked_tool_names]
            tool_risk = self._sanitize_tool_risk(get_tool_risk_routing(invoked_defs))
            force_verifier_for_tool_risk = bool(tool_risk.get("use_verifier"))

        drafter_quality = quality_func(drafter_result)
        if invoked_tool_names:
            accepted = not force_verifier_for_tool_risk
        else:
            accepted = drafter_quality >= self.quality_threshold

        # STEP 3: If quality insufficient, cascade to verifier
        if not accepted:
            if emit_switch_message and not tools_bound:
                verifier_model_name = (
                    getattr(self.verifier, "model_name", None)
                    or getattr(self.verifier, "model", None)
                    or "verifier"
                )
                switch_message = f"\n\n[CascadeFlow] Escalating to {verifier_model_name} (quality: {drafter_quality:.2f} < {self.quality_threshold})\n\n"
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=switch_message), text=switch_message
                )

            # Stream from verifier
            reason = "tool_risk" if force_verifier_for_tool_risk else "quality"
            verifier_tags = base_tags + [
                "cascadeflow:verifier",
                "verifier",
                "cascadeflow:escalated",
                f"cascadeflow:reason={reason}",
            ]
            if tool_risk and tool_risk.get("max_risk_name"):
                verifier_tags.append(f"cascadeflow:toolrisk={tool_risk['max_risk_name']}")

            for chunk in self.verifier.stream(
                messages,
                **{
                    **merged_kwargs,
                    "tags": verifier_tags,
                    "metadata": {
                        **base_metadata,
                        "cascadeflow": {
                            **base_metadata["cascadeflow"],
                            "decision": "verify",
                            "role": "verifier",
                            "reason": reason,
                            "tool_risk": tool_risk,
                        },
                    },
                },
            ):
                chunk_text = chunk.content if isinstance(chunk.content, str) else ""
                yield ChatGenerationChunk(message=chunk, text=chunk_text)
            return

        if tools_bound:
            for chunk in drafter_chunks:
                chunk_text = chunk.content if isinstance(chunk.content, str) else ""
                yield ChatGenerationChunk(message=chunk, text=chunk_text)

        # Calculate cost metadata (streaming mode has limited token usage data)
        drafter_model_name = (
            getattr(self.drafter, "model_name", None)
            or getattr(self.drafter, "model", None)
            or self.drafter._llm_type
        )

        verifier_model_name = (
            getattr(self.verifier, "model_name", None)
            or getattr(self.verifier, "model", None)
            or self.verifier._llm_type
        )

        # Create verifier result if escalated (synthetic, no usage data in streaming)
        verifier_result = None
        if not accepted:
            verifier_result = ChatResult(generations=[], llm_output={})

        cost_metadata = create_cost_metadata(
            drafter_result,
            verifier_result,
            drafter_model_name,
            verifier_model_name,
            accepted,
            drafter_quality,
            self.cost_tracking_provider,
        )

        # Store cascade result
        latency_ms = (time.time() - start_time) * 1000
        self._last_cascade_result = CascadeResult(
            content=drafter_content,
            model_used="drafter" if accepted else "verifier",
            drafter_quality=drafter_quality,
            accepted=accepted,
            drafter_cost=cost_metadata["drafter_cost"],
            verifier_cost=cost_metadata["verifier_cost"],
            total_cost=cost_metadata["total_cost"],
            savings_percentage=cost_metadata["savings_percentage"],
            latency_ms=latency_ms,
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Async stream responses with optimistic drafter execution.

        Uses the proven cascade streaming pattern:
        1. Stream drafter optimistically (user sees real-time output)
        2. Collect chunks and check quality after completion
        3. If quality insufficient: show switch message + stream verifier

        Args:
            messages: Input messages
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional arguments

        Yields:
            ChatGenerationChunk instances with streaming content
        """
        start_time = time.time()

        # Merge bind kwargs with call kwargs
        merged_kwargs = {**self._bind_kwargs, **kwargs}
        if stop:
            merged_kwargs["stop"] = stop
        base_tags = (merged_kwargs.get("tags") or []) + ["cascadeflow"]
        base_metadata = {
            **(merged_kwargs.get("metadata") or {}),
            "cascadeflow": {
                **(
                    merged_kwargs.get("metadata", {}).get("cascadeflow", {})
                    if isinstance(merged_kwargs.get("metadata"), dict)
                    else {}
                ),
                "integration": "langchain",
                "streaming": True,
            },
        }
        emit_switch_message = bool(base_metadata.get("cascadeflow_emit_switch_message"))

        # STEP 0: PreRouter - Check if we should bypass cascade
        use_cascade = True
        routing_decision = None

        if self.enable_pre_router and self.pre_router:
            # Extract query text from messages
            query_text = "\n".join(
                [msg.content if isinstance(msg.content, str) else "" for msg in messages]
            )

            # Route based on complexity
            routing_decision = await self.pre_router.route(query_text)
            from .routers.base import RoutingStrategy

            use_cascade = routing_decision["strategy"] == RoutingStrategy.CASCADE

            # If direct routing, stream verifier only
            if not use_cascade:
                async for chunk in self.verifier.astream(
                    messages,
                    **{
                        **merged_kwargs,
                        "tags": base_tags
                        + ["cascadeflow:direct", "cascadeflow:verifier", "verifier"],
                        "metadata": {
                            **base_metadata,
                            "cascadeflow": {
                                **base_metadata["cascadeflow"],
                                "decision": "direct",
                                "role": "verifier",
                            },
                        },
                    },
                ):
                    yield ChatGenerationChunk(
                        message=chunk, text=chunk.content if isinstance(chunk.content, str) else ""
                    )
                return

        tools_bound = bool(self._bound_tool_defs)
        drafter_chunks: list[AIMessageChunk] = []
        drafter_content = ""

        async for chunk in self.drafter.astream(
            messages,
            **{
                **merged_kwargs,
                "tags": base_tags + ["cascadeflow:drafter", "drafter"],
                "metadata": {
                    **base_metadata,
                    "cascadeflow": {
                        **base_metadata["cascadeflow"],
                        "decision": "draft",
                        "role": "drafter",
                    },
                },
            },
        ):
            chunk_text = chunk.content if isinstance(chunk.content, str) else ""
            drafter_content += chunk_text
            drafter_chunks.append(chunk)
            if not tools_bound:
                yield ChatGenerationChunk(message=chunk, text=chunk_text)

        # STEP 2: Quality check after drafter completes
        combined_chunk = None
        for c in drafter_chunks:
            combined_chunk = c if combined_chunk is None else combined_chunk + c

        combined_message = (
            AIMessage(
                content=(
                    combined_chunk.content
                    if combined_chunk and isinstance(combined_chunk.content, str)
                    else drafter_content
                ),
                additional_kwargs=(
                    getattr(combined_chunk, "additional_kwargs", {}) if combined_chunk else {}
                ),
                tool_calls=getattr(combined_chunk, "tool_calls", None) if combined_chunk else None,
                invalid_tool_calls=(
                    getattr(combined_chunk, "invalid_tool_calls", None) if combined_chunk else None
                ),
                response_metadata=(
                    getattr(combined_chunk, "response_metadata", {}) if combined_chunk else {}
                ),
            )
            if combined_chunk
            else AIMessage(content=drafter_content)
        )
        drafter_result = ChatResult(
            generations=[ChatGeneration(text=drafter_content, message=combined_message)],
            llm_output={},
        )

        quality_func = self.quality_validator or calculate_quality
        drafter_tool_calls = extract_tool_calls(drafter_result)
        invoked_tool_names = self._extract_tool_call_names(drafter_tool_calls)
        tool_risk = None
        force_verifier_for_tool_risk = False
        if invoked_tool_names:
            invoked_defs = [self._get_tool_def_for_name(n) for n in invoked_tool_names]
            tool_risk = self._sanitize_tool_risk(get_tool_risk_routing(invoked_defs))
            force_verifier_for_tool_risk = bool(tool_risk.get("use_verifier"))

        drafter_quality = quality_func(drafter_result)
        if invoked_tool_names:
            accepted = not force_verifier_for_tool_risk
        else:
            accepted = drafter_quality >= self.quality_threshold

        # STEP 3: If quality insufficient, cascade to verifier
        if not accepted:
            if emit_switch_message and not tools_bound:
                verifier_model_name = (
                    getattr(self.verifier, "model_name", None)
                    or getattr(self.verifier, "model", None)
                    or "verifier"
                )
                switch_message = f"\n\n[CascadeFlow] Escalating to {verifier_model_name} (quality: {drafter_quality:.2f} < {self.quality_threshold})\n\n"
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=switch_message), text=switch_message
                )

            # Stream from verifier
            reason = "tool_risk" if force_verifier_for_tool_risk else "quality"
            verifier_tags = base_tags + [
                "cascadeflow:verifier",
                "verifier",
                "cascadeflow:escalated",
                f"cascadeflow:reason={reason}",
            ]
            if tool_risk and tool_risk.get("max_risk_name"):
                verifier_tags.append(f"cascadeflow:toolrisk={tool_risk['max_risk_name']}")

            async for chunk in self.verifier.astream(
                messages,
                **{
                    **merged_kwargs,
                    "tags": verifier_tags,
                    "metadata": {
                        **base_metadata,
                        "cascadeflow": {
                            **base_metadata["cascadeflow"],
                            "decision": "verify",
                            "role": "verifier",
                            "reason": reason,
                            "tool_risk": tool_risk,
                        },
                    },
                },
            ):
                chunk_text = chunk.content if isinstance(chunk.content, str) else ""
                yield ChatGenerationChunk(message=chunk, text=chunk_text)
            return

        if tools_bound:
            for chunk in drafter_chunks:
                chunk_text = chunk.content if isinstance(chunk.content, str) else ""
                yield ChatGenerationChunk(message=chunk, text=chunk_text)

        # Calculate cost metadata (streaming mode has limited token usage data)
        drafter_model_name = (
            getattr(self.drafter, "model_name", None)
            or getattr(self.drafter, "model", None)
            or self.drafter._llm_type
        )

        verifier_model_name = (
            getattr(self.verifier, "model_name", None)
            or getattr(self.verifier, "model", None)
            or self.verifier._llm_type
        )

        # Create verifier result if escalated (synthetic, no usage data in streaming)
        verifier_result = None
        if not accepted:
            verifier_result = ChatResult(generations=[], llm_output={})

        cost_metadata = create_cost_metadata(
            drafter_result,
            verifier_result,
            drafter_model_name,
            verifier_model_name,
            accepted,
            drafter_quality,
            self.cost_tracking_provider,
        )

        # Store cascade result
        latency_ms = (time.time() - start_time) * 1000
        self._last_cascade_result = CascadeResult(
            content=drafter_content,
            model_used="drafter" if accepted else "verifier",
            drafter_quality=drafter_quality,
            accepted=accepted,
            drafter_cost=cost_metadata["drafter_cost"],
            verifier_cost=cost_metadata["verifier_cost"],
            total_cost=cost_metadata["total_cost"],
            savings_percentage=cost_metadata["savings_percentage"],
            latency_ms=latency_ms,
        )

    def bind(self, **kwargs: Any) -> "CascadeFlow":
        """Create a new CascadeFlow with bound parameters.

        Args:
            **kwargs: Parameters to bind

        Returns:
            New CascadeFlow instance with merged parameters
        """
        # Merge new kwargs with existing ones
        merged_kwargs = {**self._bind_kwargs, **kwargs}

        # Remove callbacks from bind_kwargs - they should be passed per-invocation, not bound
        # This prevents duplicate callback parameter errors in LangChain's internals
        merged_kwargs.pop("callbacks", None)

        new_instance = CascadeFlow(
            drafter=self.drafter,
            verifier=self.verifier,
            quality_threshold=self.quality_threshold,
            enable_cost_tracking=self.enable_cost_tracking,
            cost_tracking_provider=self.cost_tracking_provider,
            quality_validator=self.quality_validator,
            enable_pre_router=self.enable_pre_router,
            pre_router=self.pre_router,
            cascade_complexities=self.cascade_complexities,
        )
        new_instance._bind_kwargs = merged_kwargs
        new_instance._bound_tool_defs = self._bound_tool_defs[:] if self._bound_tool_defs else None

        return new_instance

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> "CascadeFlow":
        """Bind tools to both drafter and verifier models.

        This method overrides the inherited BaseChatModel.bind_tools() to ensure
        tools are properly bound to both the drafter and verifier models used in
        the cascade. The inherited version would only wrap the CascadeFlow instance,
        leaving the internal models without tool access.

        Args:
            tools: Sequence of tools to bind (dicts, types, callables, or BaseTool instances)
            tool_choice: The tool to use (e.g., "any", "auto", or specific tool name)
            **kwargs: Additional arguments to pass to bind_tools()

        Returns:
            New CascadeFlow instance with tools bound to both drafter and verifier

        Example:
            >>> from langchain_openai import ChatOpenAI
            >>> from cascadeflow.langchain import CascadeFlow
            >>>
            >>> drafter = ChatOpenAI(model='gpt-4o-mini')
            >>> verifier = ChatOpenAI(model='gpt-4o')
            >>> cascade = CascadeFlow(drafter=drafter, verifier=verifier)
            >>>
            >>> # Bind tools to both models
            >>> tools = [{"name": "calculator", "description": "...", "parameters": {...}}]
            >>> cascade_with_tools = cascade.bind_tools(tools)
            >>> result = await cascade_with_tools.ainvoke("What is 15 + 27?")
        """
        # Check if models support bind_tools
        if not hasattr(self.drafter, "bind_tools"):
            raise AttributeError(
                f"Drafter model ({type(self.drafter).__name__}) does not support bind_tools(). "
                "Ensure you're using a model that supports tool calling."
            )
        if not hasattr(self.verifier, "bind_tools"):
            raise AttributeError(
                f"Verifier model ({type(self.verifier).__name__}) does not support bind_tools(). "
                "Ensure you're using a model that supports tool calling."
            )

        # Bind tools to both drafter and verifier
        bound_drafter = self.drafter.bind_tools(tools, tool_choice=tool_choice, **kwargs)
        bound_verifier = self.verifier.bind_tools(tools, tool_choice=tool_choice, **kwargs)

        # Create new CascadeFlow with bound models
        new_instance = CascadeFlow(
            drafter=bound_drafter,
            verifier=bound_verifier,
            quality_threshold=self.quality_threshold,
            enable_cost_tracking=self.enable_cost_tracking,
            cost_tracking_provider=self.cost_tracking_provider,
            quality_validator=self.quality_validator,
            enable_pre_router=self.enable_pre_router,
            pre_router=self.pre_router,
            cascade_complexities=self.cascade_complexities,
        )
        # Preserve any bound kwargs
        new_instance._bind_kwargs = self._bind_kwargs.copy()
        new_instance._bound_tool_defs = self._normalize_tool_defs(tools)

        return new_instance

    def with_structured_output(
        self,
        schema: Any,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> "CascadeFlow":
        """Bind structured output schema to both drafter and verifier models.

        This method overrides the inherited BaseChatModel.with_structured_output() to
        ensure the schema is properly bound to both the drafter and verifier models used
        in the cascade. The inherited version would only wrap the CascadeFlow instance,
        leaving the internal models without schema access.

        Args:
            schema: The output schema (Pydantic model, TypedDict, or JSON schema dict)
            include_raw: Whether to include the raw message alongside the parsed output
            **kwargs: Additional arguments to pass to with_structured_output()

        Returns:
            New CascadeFlow instance with structured output bound to both models

        Example:
            >>> from langchain_openai import ChatOpenAI
            >>> from cascadeflow.langchain import CascadeFlow
            >>> from pydantic import BaseModel, Field
            >>>
            >>> class User(BaseModel):
            ...     name: str = Field(description="User's name")
            ...     age: int = Field(description="User's age")
            ...     email: str = Field(description="User's email")
            >>>
            >>> drafter = ChatOpenAI(model='gpt-4o-mini')
            >>> verifier = ChatOpenAI(model='gpt-4o')
            >>> cascade = CascadeFlow(drafter=drafter, verifier=verifier)
            >>>
            >>> # Bind structured output to both models
            >>> cascade_structured = cascade.with_structured_output(User)
            >>> user = await cascade_structured.ainvoke("Extract: John, 28, john@email.com")
            >>> print(user.name)  # "John"
        """
        # Check if models support with_structured_output
        if not hasattr(self.drafter, "with_structured_output"):
            raise AttributeError(
                f"Drafter model ({type(self.drafter).__name__}) does not support "
                "with_structured_output(). Ensure you're using a model that supports "
                "structured output."
            )
        if not hasattr(self.verifier, "with_structured_output"):
            raise AttributeError(
                f"Verifier model ({type(self.verifier).__name__}) does not support "
                "with_structured_output(). Ensure you're using a model that supports "
                "structured output."
            )

        # Bind structured output to both drafter and verifier
        bound_drafter = self.drafter.with_structured_output(
            schema, include_raw=include_raw, **kwargs
        )
        bound_verifier = self.verifier.with_structured_output(
            schema, include_raw=include_raw, **kwargs
        )

        # Create new CascadeFlow with bound models
        new_instance = CascadeFlow(
            drafter=bound_drafter,
            verifier=bound_verifier,
            quality_threshold=self.quality_threshold,
            enable_cost_tracking=self.enable_cost_tracking,
            cost_tracking_provider=self.cost_tracking_provider,
            quality_validator=self.quality_validator,
            enable_pre_router=self.enable_pre_router,
            pre_router=self.pre_router,
            cascade_complexities=self.cascade_complexities,
        )
        # Preserve any bound kwargs
        new_instance._bind_kwargs = self._bind_kwargs.copy()
        new_instance._bound_tool_defs = self._bound_tool_defs[:] if self._bound_tool_defs else None

        return new_instance

    def _normalize_tool_defs(self, tools: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if tools is None:
            return out
        if isinstance(tools, dict):
            tool_list = [tools]
        elif isinstance(tools, list):
            tool_list = tools
        else:
            # Best-effort: treat as iterable of tools, otherwise single tool instance.
            try:
                tool_list = list(tools)
            except TypeError:
                tool_list = [tools]
        for t in tool_list:
            if isinstance(t, dict):
                fn = t.get("function") if isinstance(t.get("function"), dict) else None
                name = t.get("name") or (fn.get("name") if fn else None)
                if name:
                    description = (
                        t.get("description") or (fn.get("description") if fn else "") or ""
                    )
                    out.append({"name": name, "description": description})
                continue
            name = getattr(t, "name", None)
            description = getattr(t, "description", None)
            if name:
                out.append({"name": name, "description": description or ""})
        return out

    def _get_tool_def_for_name(self, name: str) -> dict[str, Any]:
        # If we have bound tool defs, prefer their description.
        if self._bound_tool_defs:
            for t in self._bound_tool_defs:
                if t.get("name") == name:
                    return t
        return {"name": name, "description": ""}

    def _extract_tool_call_names(self, tool_calls: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for c in tool_calls or []:
            n = c.get("name")
            if isinstance(n, str) and n:
                names.append(n)
                continue
            fn = c.get("function") or {}
            fn_name = fn.get("name")
            if isinstance(fn_name, str) and fn_name:
                names.append(fn_name)
        # Preserve order, dedupe
        seen: set[str] = set()
        out: list[str] = []
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
        return out

    def _sanitize_tool_risk(self, routing: dict[str, Any]) -> dict[str, Any]:
        """Ensure tool-risk routing metadata is JSON-safe for LangSmith traces."""
        if not routing:
            return {}
        return {
            "max_risk_name": routing.get("max_risk_name"),
            "use_verifier": bool(routing.get("use_verifier")),
            "classifications": routing.get("classifications") or {},
            "high_risk_tools": routing.get("high_risk_tools") or [],
        }

    def _route_query_sync(self, query_text: str) -> Optional[dict[str, Any]]:
        """Run the (async) PreRouter from sync code paths.

        LangChain can call sync `_generate`/`_stream` in non-async contexts. Our
        PreRouter API is async, so we need a bridge.
        """
        if not (self.enable_pre_router and self.pre_router):
            return None

        try:
            result = self.pre_router.route(query_text)
            if not inspect.isawaitable(result):
                return result

            # Normal sync usage: no running event loop.
            try:
                asyncio.get_running_loop()
                # If a loop is already running in this thread, we can't blockingly
                # await. Fall back to "use cascade" behavior by skipping pre-router.
                return None
            except RuntimeError:
                return asyncio.run(result)
        except Exception:
            # Pre-router should never break generation; fall back safely.
            return None


# Helper function for convenience
def with_cascade(
    drafter: BaseChatModel, verifier: BaseChatModel, quality_threshold: float = 0.7, **kwargs: Any
) -> CascadeFlow:
    """Create a CascadeFlow wrapper (convenience function).

    Args:
        drafter: The drafter model (cheap, fast)
        verifier: The verifier model (expensive, accurate)
        quality_threshold: Quality threshold for accepting drafter responses
        **kwargs: Additional CascadeFlow configuration

    Returns:
        CascadeFlow instance
    """
    return CascadeFlow(
        drafter=drafter, verifier=verifier, quality_threshold=quality_threshold, **kwargs
    )
