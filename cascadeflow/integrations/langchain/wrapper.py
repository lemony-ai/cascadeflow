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

import time
from typing import Any, AsyncIterator, Iterator, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from .types import CascadeResult
from .utils import calculate_quality, create_cost_metadata


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
    cost_tracking_provider: str = "langsmith"
    quality_validator: Optional[Any] = None
    enable_pre_router: bool = True
    pre_router: Optional[Any] = None
    cascade_complexities: list[str] = ["trivial", "simple", "moderate"]

    # Private state
    _last_cascade_result: Optional[CascadeResult] = None
    _bind_kwargs: dict[str, Any] = {}

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        drafter: BaseChatModel,
        verifier: BaseChatModel,
        quality_threshold: float = 0.7,
        enable_cost_tracking: bool = True,
        cost_tracking_provider: str = "langsmith",
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
            routing_decision = self.pre_router.route(query_text)
            from .routers.base import RoutingStrategy

            use_cascade = routing_decision["strategy"] == RoutingStrategy.CASCADE

            # If direct routing, skip drafter and go straight to verifier
            if not use_cascade:
                # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
                existing_tags = safe_kwargs.get("tags", [])
                verifier_tags = existing_tags + ["verifier"] if existing_tags else ["verifier"]
                verifier_llm_result = self.verifier.generate(
                    [messages],
                    stop=stop,
                    callbacks=callbacks,
                    **{**safe_kwargs, "tags": verifier_tags},
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
        existing_tags = safe_kwargs.get("tags", [])
        drafter_tags = existing_tags + ["drafter"] if existing_tags else ["drafter"]
        drafter_llm_result = self.drafter.generate(
            [messages], stop=stop, callbacks=callbacks, **{**safe_kwargs, "tags": drafter_tags}
        )

        # Convert LLMResult to ChatResult
        drafter_result = ChatResult(
            generations=drafter_llm_result.generations[0], llm_output=drafter_llm_result.llm_output
        )

        # Calculate drafter quality
        quality_func = self.quality_validator or calculate_quality
        drafter_quality = quality_func(drafter_result)

        # STEP 2: Check quality threshold
        accepted = drafter_quality >= self.quality_threshold

        if accepted:
            # Quality is sufficient - use drafter response
            final_result = drafter_result
            verifier_result = None
        else:
            # Quality insufficient - execute verifier (expensive, accurate model)
            # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
            existing_tags = safe_kwargs.get("tags", [])
            verifier_tags = existing_tags + ["verifier"] if existing_tags else ["verifier"]
            verifier_llm_result = self.verifier.generate(
                [messages], stop=stop, callbacks=callbacks, **{**safe_kwargs, "tags": verifier_tags}
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
                final_result.llm_output["cascade"] = cost_metadata

                # Also inject into message's response_metadata
                if final_result.generations:
                    gen = final_result.generations[0]
                    if hasattr(gen, "message") and gen.message:
                        if not hasattr(gen.message, "response_metadata"):
                            gen.message.response_metadata = {}
                        gen.message.response_metadata["cascade"] = cost_metadata
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
                existing_tags = safe_kwargs.get("tags", [])
                verifier_tags = existing_tags + ["verifier"] if existing_tags else ["verifier"]
                verifier_llm_result = await self.verifier.agenerate(
                    [messages],
                    stop=stop,
                    callbacks=callbacks,
                    **{**safe_kwargs, "tags": verifier_tags},
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
        existing_tags = safe_kwargs.get("tags", [])
        drafter_tags = existing_tags + ["drafter"] if existing_tags else ["drafter"]
        drafter_llm_result = await self.drafter.agenerate(
            [messages], stop=stop, callbacks=callbacks, **{**safe_kwargs, "tags": drafter_tags}
        )

        # Convert LLMResult to ChatResult
        drafter_result = ChatResult(
            generations=drafter_llm_result.generations[0], llm_output=drafter_llm_result.llm_output
        )

        # Calculate drafter quality
        quality_func = self.quality_validator or calculate_quality
        drafter_quality = quality_func(drafter_result)

        # STEP 2: Check quality threshold
        accepted = drafter_quality >= self.quality_threshold

        if accepted:
            # Quality is sufficient - use drafter response
            final_result = drafter_result
            verifier_result = None
        else:
            # Quality insufficient - execute verifier (expensive, accurate model)
            # Pass only safe kwargs with explicit stop and merged tags for reliable LangSmith tracking
            existing_tags = safe_kwargs.get("tags", [])
            verifier_tags = existing_tags + ["verifier"] if existing_tags else ["verifier"]
            verifier_llm_result = await self.verifier.agenerate(
                [messages], stop=stop, callbacks=callbacks, **{**safe_kwargs, "tags": verifier_tags}
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
                final_result.llm_output["cascade"] = cost_metadata

                # Also inject into message's response_metadata
                if final_result.generations:
                    gen = final_result.generations[0]
                    if hasattr(gen, "message") and gen.message:
                        if not hasattr(gen.message, "response_metadata"):
                            gen.message.response_metadata = {}
                        gen.message.response_metadata["cascade"] = cost_metadata
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

        # STEP 0: PreRouter - Check if we should bypass cascade
        use_cascade = True
        routing_decision = None

        if self.enable_pre_router and self.pre_router:
            # Extract query text from messages
            query_text = "\n".join(
                [msg.content if isinstance(msg.content, str) else "" for msg in messages]
            )

            # Route based on complexity (sync call for sync streaming)
            routing_decision = self.pre_router.route(query_text)
            from .routers.base import RoutingStrategy

            use_cascade = routing_decision["strategy"] == RoutingStrategy.CASCADE

            # If direct routing, stream verifier only
            if not use_cascade:
                for chunk in self.verifier.stream(messages, **merged_kwargs):
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(content=chunk.content),
                        text=chunk.content if isinstance(chunk.content, str) else "",
                    )
                return

        # STEP 1: Stream drafter optimistically
        drafter_chunks: list[ChatGenerationChunk] = []
        drafter_content = ""

        # Stream from drafter in real-time
        for chunk in self.drafter.stream(messages, **merged_kwargs):
            # Extract text content from chunk
            chunk_text = chunk.content if isinstance(chunk.content, str) else ""
            drafter_content += chunk_text

            # Create ChatGenerationChunk
            gen_chunk = ChatGenerationChunk(
                message=AIMessageChunk(content=chunk_text), text=chunk_text
            )
            drafter_chunks.append(gen_chunk)

            # Yield chunk immediately for real-time streaming
            yield gen_chunk

        # STEP 2: Quality check after drafter completes
        drafter_result = ChatResult(
            generations=[
                ChatGeneration(text=drafter_content, message=AIMessage(content=drafter_content))
            ],
            llm_output={},
        )

        quality_func = self.quality_validator or calculate_quality
        drafter_quality = quality_func(drafter_result)
        accepted = drafter_quality >= self.quality_threshold

        # STEP 3: If quality insufficient, cascade to verifier
        if not accepted:
            # Emit switch notification
            verifier_model_name = (
                getattr(self.verifier, "model_name", None)
                or getattr(self.verifier, "model", None)
                or "verifier"
            )
            switch_message = f"\n\n⤴ Cascading to {verifier_model_name} (quality: {drafter_quality:.2f} < {self.quality_threshold})\n\n"

            yield ChatGenerationChunk(
                message=AIMessageChunk(content=switch_message), text=switch_message
            )

            # Stream from verifier
            for chunk in self.verifier.stream(messages, **merged_kwargs):
                chunk_text = chunk.content if isinstance(chunk.content, str) else ""
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=chunk_text), text=chunk_text
                )

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
                async for chunk in self.verifier.astream(messages, **merged_kwargs):
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(content=chunk.content),
                        text=chunk.content if isinstance(chunk.content, str) else "",
                    )
                return

        # STEP 1: Stream drafter optimistically
        drafter_chunks: list[ChatGenerationChunk] = []
        drafter_content = ""

        # Stream from drafter in real-time
        async for chunk in self.drafter.astream(messages, **merged_kwargs):
            # Extract text content from chunk
            chunk_text = chunk.content if isinstance(chunk.content, str) else ""
            drafter_content += chunk_text

            # Create ChatGenerationChunk
            gen_chunk = ChatGenerationChunk(
                message=AIMessageChunk(content=chunk_text), text=chunk_text
            )
            drafter_chunks.append(gen_chunk)

            # Yield chunk immediately for real-time streaming
            yield gen_chunk

        # STEP 2: Quality check after drafter completes
        drafter_result = ChatResult(
            generations=[
                ChatGeneration(text=drafter_content, message=AIMessage(content=drafter_content))
            ],
            llm_output={},
        )

        quality_func = self.quality_validator or calculate_quality
        drafter_quality = quality_func(drafter_result)
        accepted = drafter_quality >= self.quality_threshold

        # STEP 3: If quality insufficient, cascade to verifier
        if not accepted:
            # Emit switch notification
            verifier_model_name = (
                getattr(self.verifier, "model_name", None)
                or getattr(self.verifier, "model", None)
                or "verifier"
            )
            switch_message = f"\n\n⤴ Cascading to {verifier_model_name} (quality: {drafter_quality:.2f} < {self.quality_threshold})\n\n"

            yield ChatGenerationChunk(
                message=AIMessageChunk(content=switch_message), text=switch_message
            )

            # Stream from verifier
            async for chunk in self.verifier.astream(messages, **merged_kwargs):
                chunk_text = chunk.content if isinstance(chunk.content, str) else ""
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=chunk_text), text=chunk_text
                )

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

        return new_instance


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
