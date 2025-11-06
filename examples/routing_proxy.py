"""
CascadeFlow Routing Proxy - MVP Implementation
================================================

A transparent routing proxy that provides API-compatible endpoints for:
- Anthropic Messages API (/v1/messages)
- OpenAI Chat Completions API (/v1/chat/completions)

With intelligent cascade routing and automatic cost optimization.

Key Features:
- Drop-in replacement for Claude Code and other AI tools
- Automatic cascade routing (try cheap models first, escalate if needed)
- Quality-based verification
- Both streaming and non-streaming support
- API key authentication
- Cost tracking and monitoring

Setup:
    pip install cascadeflow[all] fastapi uvicorn
    export CASCADEFLOW_API_KEY="your-secret-key"
    export OPENAI_API_KEY="sk-..."
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/routing_proxy.py

Claude Code Configuration:
    export ANTHROPIC_BASE_URL="http://localhost:8000"
    export ANTHROPIC_API_KEY="your-cascadeflow-api-key"

Documentation:
    📖 Architecture: docs/ROUTING_PROXY_ARCHITECTURE.md
    📖 Fact Check: docs/ROUTING_PROXY_FACT_CHECK.md
    📖 Implementation Plan: docs/ROUTING_PROXY_IMPLEMENTATION_PLAN.md
"""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Union

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cascadeflow import CascadeAgent, ModelConfig

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ANTHROPIC API MODELS
# ═══════════════════════════════════════════════════════════════════════════


class AnthropicMessageRole(str, Enum):
    """Message role in Anthropic API."""

    user = "user"
    assistant = "assistant"


class AnthropicContentBlock(BaseModel):
    """Content block in Anthropic message."""

    type: Literal["text"] = "text"
    text: str


class AnthropicMessage(BaseModel):
    """Message in Anthropic API format."""

    role: AnthropicMessageRole
    content: Union[str, List[AnthropicContentBlock]]


class AnthropicMessagesRequest(BaseModel):
    """Request model for Anthropic /v1/messages endpoint."""

    model: str = Field(..., description="Model identifier")
    messages: List[AnthropicMessage] = Field(..., description="List of messages")
    max_tokens: int = Field(1024, description="Maximum tokens to generate", ge=1)
    temperature: Optional[float] = Field(1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=0)
    stream: Optional[bool] = Field(False, description="Enable streaming")
    system: Optional[str] = Field(None, description="System prompt")
    metadata: Optional[Dict[str, Any]] = Field(None)

    class Config:
        schema_extra = {
            "example": {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "What is machine learning?"}],
                "max_tokens": 1024,
                "temperature": 1.0,
                "stream": False,
            }
        }


class AnthropicUsage(BaseModel):
    """Usage statistics in Anthropic response."""

    input_tokens: int
    output_tokens: int


class AnthropicMessagesResponse(BaseModel):
    """Response model for Anthropic /v1/messages endpoint."""

    id: str = Field(..., description="Unique message ID")
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: List[AnthropicContentBlock]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: AnthropicUsage


# ═══════════════════════════════════════════════════════════════════════════
# OPENAI API MODELS
# ═══════════════════════════════════════════════════════════════════════════


class OpenAIRole(str, Enum):
    """Message role in OpenAI API."""

    system = "system"
    user = "user"
    assistant = "assistant"


class OpenAIMessage(BaseModel):
    """Message in OpenAI API format."""

    role: OpenAIRole
    content: str
    name: Optional[str] = None


class OpenAIChatCompletionRequest(BaseModel):
    """Request model for OpenAI /v1/chat/completions endpoint."""

    model: str = Field(..., description="Model identifier")
    messages: List[OpenAIMessage] = Field(..., description="List of messages")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate", ge=1)
    temperature: Optional[float] = Field(1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(1, ge=1)
    stream: Optional[bool] = Field(False, description="Enable streaming")
    stop: Optional[Union[str, List[str]]] = Field(None)
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = Field(None)
    user: Optional[str] = Field(None)

    class Config:
        schema_extra = {
            "example": {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "What is machine learning?"}],
                "max_tokens": 1024,
                "temperature": 0.7,
                "stream": False,
            }
        }


class OpenAIChoice(BaseModel):
    """Choice in OpenAI response."""

    index: int
    message: OpenAIMessage
    finish_reason: Optional[str] = None


class OpenAIUsage(BaseModel):
    """Usage statistics in OpenAI response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIChatCompletionResponse(BaseModel):
    """Response model for OpenAI /v1/chat/completions endpoint."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: OpenAIUsage
    system_fingerprint: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# STREAMING MODELS
# ═══════════════════════════════════════════════════════════════════════════


class OpenAIStreamDelta(BaseModel):
    """Delta in OpenAI streaming response."""

    role: Optional[str] = None
    content: Optional[str] = None


class OpenAIStreamChoice(BaseModel):
    """Choice in OpenAI streaming response."""

    index: int
    delta: OpenAIStreamDelta
    finish_reason: Optional[str] = None


class OpenAIChatCompletionChunk(BaseModel):
    """Chunk in OpenAI streaming response."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: List[OpenAIStreamChoice]


class AnthropicStreamEvent(BaseModel):
    """Event in Anthropic streaming response."""

    type: str


class AnthropicMessageStartEvent(AnthropicStreamEvent):
    """Message start event in Anthropic streaming."""

    type: Literal["message_start"] = "message_start"
    message: AnthropicMessagesResponse


class AnthropicContentBlockStartEvent(AnthropicStreamEvent):
    """Content block start event."""

    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: AnthropicContentBlock


class AnthropicContentBlockDelta(BaseModel):
    """Delta in content block."""

    type: Literal["text_delta"] = "text_delta"
    text: str


class AnthropicContentBlockDeltaEvent(AnthropicStreamEvent):
    """Content block delta event."""

    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: AnthropicContentBlockDelta


class AnthropicContentBlockStopEvent(AnthropicStreamEvent):
    """Content block stop event."""

    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class AnthropicMessageDelta(BaseModel):
    """Delta in message."""

    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None


class AnthropicMessageDeltaEvent(AnthropicStreamEvent):
    """Message delta event."""

    type: Literal["message_delta"] = "message_delta"
    delta: AnthropicMessageDelta
    usage: Optional[AnthropicUsage] = None


class AnthropicMessageStopEvent(AnthropicStreamEvent):
    """Message stop event."""

    type: Literal["message_stop"] = "message_stop"


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════════

agent: Optional[CascadeAgent] = None
api_key: Optional[str] = None
stats = {
    "total_requests": 0,
    "anthropic_requests": 0,
    "openai_requests": 0,
    "total_cost": 0.0,
    "cascade_used": 0,
    "models_used": {},
    "start_time": None,
}


# ═══════════════════════════════════════════════════════════════════════════
# API KEY VALIDATION
# ═══════════════════════════════════════════════════════════════════════════


def validate_api_key(authorization: Optional[str] = None, x_api_key: Optional[str] = None) -> bool:
    """Validate API key from Authorization header or x-api-key header."""
    if not api_key:
        # No API key configured, allow all requests
        return True

    # Check Authorization header (Bearer token)
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            if token == api_key:
                return True

    # Check x-api-key header
    if x_api_key and x_api_key == api_key:
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def convert_anthropic_messages_to_query(messages: List[AnthropicMessage], system: Optional[str] = None) -> str:
    """Convert Anthropic messages format to a simple query string."""
    parts = []

    if system:
        parts.append(f"System: {system}")

    for msg in messages:
        role = msg.role.value
        if isinstance(msg.content, str):
            content = msg.content
        else:
            # Extract text from content blocks
            content = " ".join(block.text for block in msg.content if block.type == "text")

        parts.append(f"{role.capitalize()}: {content}")

    return "\n\n".join(parts)


def convert_openai_messages_to_query(messages: List[OpenAIMessage]) -> str:
    """Convert OpenAI messages format to a simple query string."""
    parts = []

    for msg in messages:
        role = msg.role.value
        parts.append(f"{role.capitalize()}: {msg.content}")

    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# LIFESPAN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global agent, api_key, stats

    # Startup
    logger.info("🚀 Starting CascadeFlow Routing Proxy...")

    # Load API key
    api_key = os.getenv("CASCADEFLOW_API_KEY")
    if api_key:
        logger.info("✓ API key authentication enabled")
    else:
        logger.warning("⚠️  No API key configured - proxy is open to all requests")

    # Initialize agent
    try:
        models = []

        # Add models from environment
        if os.getenv("GROQ_API_KEY"):
            models.append(ModelConfig("llama-3.1-8b-instant", provider="groq", cost=0.00005))
            logger.info("✓ Groq models configured")

        if os.getenv("OPENAI_API_KEY"):
            models.extend([
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ])
            logger.info("✓ OpenAI models configured")

        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(
                ModelConfig("claude-3-5-sonnet-20241022", provider="anthropic", cost=0.003)
            )
            logger.info("✓ Anthropic models configured")

        if not models:
            raise ValueError(
                "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY"
            )

        agent = CascadeAgent(models=models)
        stats["start_time"] = datetime.now()

        logger.info(f"✓ Agent initialized with {len(models)} models")
        logger.info("✓ Routing proxy ready at http://localhost:8000")
        logger.info("✓ Anthropic API: http://localhost:8000/v1/messages")
        logger.info("✓ OpenAI API: http://localhost:8000/v1/chat/completions")
        logger.info("✓ API docs: http://localhost:8000/docs")

    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down CascadeFlow Routing Proxy...")
    logger.info(
        f"Final stats: {stats['total_requests']} requests, ${stats['total_cost']:.4f} total cost"
    )


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════


app = FastAPI(
    title="CascadeFlow Routing Proxy",
    description="Transparent routing proxy with API-compatible endpoints for cost optimization",
    version="0.1.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "CascadeFlow Routing Proxy",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "anthropic": "/v1/messages",
            "openai": "/v1/chat/completions",
            "stats": "/api/stats",
        },
        "cascade_routing": "enabled",
        "authentication": "enabled" if api_key else "disabled",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    providers = []
    if os.getenv("OPENAI_API_KEY"):
        providers.append("openai")
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.getenv("GROQ_API_KEY"):
        providers.append("groq")

    return {
        "status": "healthy" if agent is not None else "unhealthy",
        "version": "0.1.0",
        "agent_initialized": agent is not None,
        "providers_available": providers,
        "authentication": "enabled" if api_key else "disabled",
    }


@app.post("/v1/messages", tags=["Anthropic API"])
async def anthropic_messages(
    request: AnthropicMessagesRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    Anthropic Messages API endpoint (/v1/messages).

    Drop-in replacement for api.anthropic.com/v1/messages
    """
    # Validate API key
    if not validate_api_key(authorization, x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        # Convert messages to query format
        query = convert_anthropic_messages_to_query(request.messages, request.system)

        logger.info(f"[Anthropic API] Processing request: model={request.model}, stream={request.stream}")

        # Handle streaming
        if request.stream:
            return await anthropic_stream_response(request, query)

        # Non-streaming response
        result = await agent.run(
            query=query,
            max_tokens=request.max_tokens,
            temperature=request.temperature or 1.0,
        )

        # Update stats
        stats["total_requests"] += 1
        stats["anthropic_requests"] += 1
        stats["total_cost"] += result.total_cost
        if result.cascaded:
            stats["cascade_used"] += 1
        model = result.model_used
        stats["models_used"][model] = stats["models_used"].get(model, 0) + 1

        logger.info(
            f"[Anthropic API] Completed: {model}, ${result.total_cost:.6f}, "
            f"cascade={'yes' if result.cascaded else 'no'}"
        )

        # Format response in Anthropic format
        response = AnthropicMessagesResponse(
            id=f"msg_{uuid.uuid4().hex[:24]}",
            type="message",
            role="assistant",
            content=[AnthropicContentBlock(type="text", text=result.content)],
            model=request.model,  # Return requested model name for compatibility
            stop_reason="end_turn",
            usage=AnthropicUsage(
                input_tokens=100,  # Estimate
                output_tokens=len(result.content.split()) * 2  # Rough estimate
            ),
        )

        return response

    except Exception as e:
        logger.error(f"[Anthropic API] Request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def anthropic_stream_response(request: AnthropicMessagesRequest, query: str):
    """Handle streaming response for Anthropic API."""

    async def event_generator():
        """Generate Server-Sent Events for Anthropic streaming."""
        try:
            message_id = f"msg_{uuid.uuid4().hex[:24]}"

            # Send message_start event
            start_event = {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": request.model,
                    "usage": {"input_tokens": 100, "output_tokens": 0}
                }
            }
            yield f"event: message_start\ndata: {json.dumps(start_event)}\n\n"

            # Send content_block_start event
            block_start = {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""}
            }
            yield f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n"

            # Stream content
            total_cost = 0.0
            model_used = None
            accumulated_text = ""

            if agent.can_stream:
                async for event in agent.text_streaming_manager.stream(
                    query=query,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature or 1.0,
                ):
                    if event.type.value == "chunk":
                        text = event.content
                        accumulated_text += text
                        delta_event = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "text_delta", "text": text}
                        }
                        yield f"event: content_block_delta\ndata: {json.dumps(delta_event)}\n\n"

                    elif event.type.value == "complete":
                        result = event.data.get("result", {})
                        total_cost = result.get("total_cost", 0.0)
                        model_used = result.get("model_used", "unknown")
            else:
                # Fallback: non-streaming
                result = await agent.run(
                    query=query,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature or 1.0,
                )
                accumulated_text = result.content
                total_cost = result.total_cost
                model_used = result.model_used

                # Send as single chunk
                delta_event = {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": accumulated_text}
                }
                yield f"event: content_block_delta\ndata: {json.dumps(delta_event)}\n\n"

            # Send content_block_stop event
            block_stop = {"type": "content_block_stop", "index": 0}
            yield f"event: content_block_stop\ndata: {json.dumps(block_stop)}\n\n"

            # Send message_delta event
            output_tokens = len(accumulated_text.split()) * 2
            delta = {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": output_tokens}
            }
            yield f"event: message_delta\ndata: {json.dumps(delta)}\n\n"

            # Send message_stop event
            stop = {"type": "message_stop"}
            yield f"event: message_stop\ndata: {json.dumps(stop)}\n\n"

            # Update stats
            stats["total_requests"] += 1
            stats["anthropic_requests"] += 1
            stats["total_cost"] += total_cost
            if model_used:
                stats["models_used"][model_used] = stats["models_used"].get(model_used, 0) + 1

            logger.info(f"[Anthropic API] Stream completed: {model_used}, ${total_cost:.6f}")

        except Exception as e:
            logger.error(f"[Anthropic API] Streaming failed: {e}")
            error_event = {
                "type": "error",
                "error": {"type": "internal_error", "message": str(e)}
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/v1/chat/completions", tags=["OpenAI API"])
async def openai_chat_completions(
    request: OpenAIChatCompletionRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    OpenAI Chat Completions API endpoint (/v1/chat/completions).

    Drop-in replacement for api.openai.com/v1/chat/completions
    """
    # Validate API key
    if not validate_api_key(authorization, x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        # Convert messages to query format
        query = convert_openai_messages_to_query(request.messages)

        logger.info(f"[OpenAI API] Processing request: model={request.model}, stream={request.stream}")

        # Handle streaming
        if request.stream:
            return await openai_stream_response(request, query)

        # Non-streaming response
        result = await agent.run(
            query=query,
            max_tokens=request.max_tokens or 1024,
            temperature=request.temperature or 1.0,
        )

        # Update stats
        stats["total_requests"] += 1
        stats["openai_requests"] += 1
        stats["total_cost"] += result.total_cost
        if result.cascaded:
            stats["cascade_used"] += 1
        model = result.model_used
        stats["models_used"][model] = stats["models_used"].get(model, 0) + 1

        logger.info(
            f"[OpenAI API] Completed: {model}, ${result.total_cost:.6f}, "
            f"cascade={'yes' if result.cascaded else 'no'}"
        )

        # Format response in OpenAI format
        response = OpenAIChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,  # Return requested model name for compatibility
            choices=[
                OpenAIChoice(
                    index=0,
                    message=OpenAIMessage(role=OpenAIRole.assistant, content=result.content),
                    finish_reason="stop",
                )
            ],
            usage=OpenAIUsage(
                prompt_tokens=100,  # Estimate
                completion_tokens=len(result.content.split()) * 2,  # Rough estimate
                total_tokens=100 + len(result.content.split()) * 2,
            ),
        )

        return response

    except Exception as e:
        logger.error(f"[OpenAI API] Request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def openai_stream_response(request: OpenAIChatCompletionRequest, query: str):
    """Handle streaming response for OpenAI API."""

    async def event_generator():
        """Generate Server-Sent Events for OpenAI streaming."""
        try:
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            created = int(time.time())

            # Send initial chunk with role
            initial_chunk = OpenAIChatCompletionChunk(
                id=completion_id,
                object="chat.completion.chunk",
                created=created,
                model=request.model,
                choices=[
                    OpenAIStreamChoice(
                        index=0,
                        delta=OpenAIStreamDelta(role="assistant", content=""),
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {initial_chunk.model_dump_json()}\n\n"

            # Stream content
            total_cost = 0.0
            model_used = None

            if agent.can_stream:
                async for event in agent.text_streaming_manager.stream(
                    query=query,
                    max_tokens=request.max_tokens or 1024,
                    temperature=request.temperature or 1.0,
                ):
                    if event.type.value == "chunk":
                        text = event.content
                        chunk = OpenAIChatCompletionChunk(
                            id=completion_id,
                            object="chat.completion.chunk",
                            created=created,
                            model=request.model,
                            choices=[
                                OpenAIStreamChoice(
                                    index=0,
                                    delta=OpenAIStreamDelta(content=text),
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

                    elif event.type.value == "complete":
                        result = event.data.get("result", {})
                        total_cost = result.get("total_cost", 0.0)
                        model_used = result.get("model_used", "unknown")
            else:
                # Fallback: non-streaming
                result = await agent.run(
                    query=query,
                    max_tokens=request.max_tokens or 1024,
                    temperature=request.temperature or 1.0,
                )
                total_cost = result.total_cost
                model_used = result.model_used

                # Send as single chunk
                chunk = OpenAIChatCompletionChunk(
                    id=completion_id,
                    object="chat.completion.chunk",
                    created=created,
                    model=request.model,
                    choices=[
                        OpenAIStreamChoice(
                            index=0,
                            delta=OpenAIStreamDelta(content=result.content),
                            finish_reason=None,
                        )
                    ],
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

            # Send final chunk with finish_reason
            final_chunk = OpenAIChatCompletionChunk(
                id=completion_id,
                object="chat.completion.chunk",
                created=created,
                model=request.model,
                choices=[
                    OpenAIStreamChoice(
                        index=0, delta=OpenAIStreamDelta(), finish_reason="stop"
                    )
                ],
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"

            # Send [DONE] marker
            yield "data: [DONE]\n\n"

            # Update stats
            stats["total_requests"] += 1
            stats["openai_requests"] += 1
            stats["total_cost"] += total_cost
            if model_used:
                stats["models_used"][model_used] = stats["models_used"].get(model_used, 0) + 1

            logger.info(f"[OpenAI API] Stream completed: {model_used}, ${total_cost:.6f}")

        except Exception as e:
            logger.error(f"[OpenAI API] Streaming failed: {e}")
            # OpenAI doesn't have a standard error format for streaming
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/stats", tags=["Monitoring"])
async def get_stats():
    """Get proxy usage statistics."""
    uptime = (datetime.now() - stats["start_time"]).total_seconds() if stats["start_time"] else 0

    return {
        "total_requests": stats["total_requests"],
        "anthropic_requests": stats["anthropic_requests"],
        "openai_requests": stats["openai_requests"],
        "total_cost": stats["total_cost"],
        "cascade_used": stats["cascade_used"],
        "cascade_percentage": (
            (stats["cascade_used"] / stats["total_requests"] * 100)
            if stats["total_requests"] > 0
            else 0
        ),
        "models_used": stats["models_used"],
        "uptime_seconds": uptime,
        "cost_per_request": (
            stats["total_cost"] / stats["total_requests"] if stats["total_requests"] > 0 else 0
        ),
    }


@app.delete("/api/stats", tags=["Monitoring"])
async def reset_stats():
    """Reset statistics."""
    stats["total_requests"] = 0
    stats["anthropic_requests"] = 0
    stats["openai_requests"] = 0
    stats["total_cost"] = 0.0
    stats["cascade_used"] = 0
    stats["models_used"] = {}
    stats["start_time"] = datetime.now()

    return {"message": "Stats reset successfully"}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print("🌊 CascadeFlow Routing Proxy - MVP")
    print("=" * 70)
    print("\n📚 Features:")
    print("   ✓ Anthropic Messages API (/v1/messages)")
    print("   ✓ OpenAI Chat Completions API (/v1/chat/completions)")
    print("   ✓ Intelligent cascade routing")
    print("   ✓ Quality-based verification")
    print("   ✓ Streaming support")
    print("   ✓ API key authentication")
    print("   ✓ Cost tracking")

    print("\n🔗 Endpoints:")
    print("   • http://localhost:8000/docs - API documentation")
    print("   • http://localhost:8000/v1/messages - Anthropic API")
    print("   • http://localhost:8000/v1/chat/completions - OpenAI API")
    print("   • http://localhost:8000/api/stats - Usage statistics")

    print("\n🔑 Claude Code Setup:")
    print('   export ANTHROPIC_BASE_URL="http://localhost:8000"')
    print('   export ANTHROPIC_API_KEY="your-cascadeflow-api-key"')

    print("\n🚀 Starting server...")
    print("=" * 70 + "\n")

    uvicorn.run(
        "routing_proxy:app", host="0.0.0.0", port=8000, reload=False, log_level="info"
    )
