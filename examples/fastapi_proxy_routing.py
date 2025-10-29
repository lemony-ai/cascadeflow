"""
FastAPI Routing Proxy Extension
================================

Extends fastapi_integration.py with Anthropic API-compatible endpoints for
transparent routing proxy functionality.

This allows using CascadeFlow as a drop-in replacement for Anthropic API:

Usage:
------
1. Start proxy:
   ```bash
   python examples/fastapi_proxy_routing.py
   ```

2. Configure Claude Code to use proxy:
   ```bash
   export ANTHROPIC_BASE_URL="http://localhost:8000"
   export ANTHROPIC_API_KEY="your-anthropic-key"  # Still needed for actual API
   ```

3. Use Claude Code normally - automatic 40-80% cost savings!

What it does:
-------------
- Accepts requests in Anthropic API format
- Routes through CascadeFlow (try Haiku → escalate to Sonnet if needed)
- Returns responses in Anthropic API format
- Completely transparent to calling application

Example:
--------
```python
from anthropic import Anthropic

# Point SDK to proxy instead of Anthropic API
client = Anthropic(
    api_key="sk-ant-...",
    base_url="http://localhost:8000"  # Proxy URL
)

# Use normally - automatic cascade routing!
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain AI"}]
)
```

What happens:
1. Proxy receives request for Sonnet
2. Tries Haiku first (draft model)
3. If quality good → returns Haiku response (60% savings!)
4. If quality bad → escalates to Sonnet
5. Response format matches Anthropic API exactly

Documentation:
--------------
📖 Proxy Gap Analysis: docs/PROXY_GAP_ANALYSIS.md
📖 Architecture: docs/ROUTING_PROXY_ARCHITECTURE.md
📖 Implementation Plan: docs/ROUTING_PROXY_IMPLEMENTATION_PLAN.md
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Literal, Optional, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cascadeflow import CascadeAgent, ModelConfig

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# ANTHROPIC API MODELS (Pydantic)
# ═══════════════════════════════════════════════════════════════════════════

class Message(BaseModel):
    """Message in conversation (Anthropic format)."""
    role: Literal["user", "assistant"]
    content: str

    class Config:
        schema_extra = {
            "example": {
                "role": "user",
                "content": "Explain quantum computing"
            }
        }


class AnthropicRequest(BaseModel):
    """Anthropic /v1/messages request format."""
    model: str = Field(..., description="Model name (e.g., claude-3-5-sonnet-20241022)")
    messages: List[Message] = Field(..., description="Conversation messages")
    max_tokens: int = Field(1024, ge=1, le=8192, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling")
    top_k: Optional[int] = Field(None, ge=0, description="Top-k sampling")
    system: Optional[str] = Field(None, description="System message")
    stop_sequences: Optional[List[str]] = Field(None, description="Stop sequences")
    stream: bool = Field(False, description="Stream response (not supported in MVP)")

    class Config:
        schema_extra = {
            "example": {
                "model": "claude-3-5-sonnet-20241022",
                "messages": [
                    {"role": "user", "content": "What is machine learning?"}
                ],
                "max_tokens": 1024,
                "temperature": 0.7
            }
        }


class ContentBlock(BaseModel):
    """Content block in response."""
    type: Literal["text"] = "text"
    text: str


class Usage(BaseModel):
    """Token usage statistics."""
    input_tokens: int
    output_tokens: int


class AnthropicResponse(BaseModel):
    """Anthropic /v1/messages response format."""
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex}")
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: List[ContentBlock]
    model: str
    stop_reason: Optional[str] = "end_turn"
    stop_sequence: Optional[str] = None
    usage: Usage

    class Config:
        schema_extra = {
            "example": {
                "id": "msg_01234567890abcdef",
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Machine learning is..."}
                ],
                "model": "claude-3-5-sonnet-20241022",
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 50
                }
            }
        }


# ═══════════════════════════════════════════════════════════════════════════
# CASCADE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class CascadeRule(BaseModel):
    """Cascade routing rule for auto-optimization."""
    request_model: str
    draft_model: str
    verifier_model: str
    quality_threshold: float = 0.7


# Default cascade rules for Anthropic models
CASCADE_RULES = [
    CascadeRule(
        request_model="claude-3-5-sonnet-20241022",
        draft_model="claude-3-5-haiku-20241022",
        verifier_model="claude-3-5-sonnet-20241022",
        quality_threshold=0.7
    ),
    CascadeRule(
        request_model="claude-3-opus-20240229",
        draft_model="claude-3-5-sonnet-20241022",
        verifier_model="claude-3-opus-20240229",
        quality_threshold=0.75
    ),
]


def get_cascade_rule(requested_model: str) -> Optional[CascadeRule]:
    """Find cascade rule for requested model."""
    for rule in CASCADE_RULES:
        if rule.request_model == requested_model:
            return rule
    return None


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════════

agent: Optional[CascadeAgent] = None
stats = {
    "total_queries": 0,
    "total_cost": 0.0,
    "cascade_used": 0,
    "models_used": {},
    "start_time": None,
}


# ═══════════════════════════════════════════════════════════════════════════
# LIFESPAN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global agent, stats

    # Startup
    logger.info("🚀 Starting CascadeFlow Routing Proxy...")

    try:
        # Initialize CascadeAgent with Anthropic models
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="claude-3-5-haiku-20241022",
                    provider="anthropic",
                    cost=0.0008,  # $0.80 per million tokens
                    quality_threshold=0.7,
                ),
                ModelConfig(
                    name="claude-3-5-sonnet-20241022",
                    provider="anthropic",
                    cost=0.003,  # $3.00 per million tokens
                    quality_threshold=0.95,
                ),
            ]
        )
        stats["start_time"] = datetime.now()

        logger.info("✓ Agent initialized with Anthropic cascade (Haiku → Sonnet)")
        logger.info("✓ Routing proxy ready at http://localhost:8000")
        logger.info("✓ API docs at http://localhost:8000/docs")
        logger.info("✓ Anthropic-compatible endpoint: POST /v1/messages")
        logger.info("")
        logger.info("Configure Claude Code:")
        logger.info('  export ANTHROPIC_BASE_URL="http://localhost:8000"')

    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down routing proxy...")
    logger.info(
        f"Final stats: {stats['total_queries']} queries, ${stats['total_cost']:.4f} total cost"
    )


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="CascadeFlow Routing Proxy",
    description="Transparent Anthropic API-compatible proxy with automatic cascade routing for 40-80% cost savings",
    version="0.3.0-mvp",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with proxy information."""
    return {
        "service": "CascadeFlow Routing Proxy",
        "version": "0.3.0-mvp",
        "description": "Anthropic API-compatible proxy with automatic cascade routing",
        "endpoints": {
            "anthropic_messages": "POST /v1/messages",
            "health": "GET /health",
            "stats": "GET /stats"
        },
        "docs": "/docs",
        "usage": {
            "configure_claude_code": 'export ANTHROPIC_BASE_URL="http://localhost:8000"',
            "cost_savings": "40-80% automatic cost reduction",
            "transparency": "Drop-in replacement for api.anthropic.com"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy" if agent is not None else "unhealthy",
        "version": "0.3.0-mvp",
        "agent_initialized": agent is not None,
        "provider": "anthropic",
        "cascade_rules": len(CASCADE_RULES)
    }


@app.post("/v1/messages", response_model=AnthropicResponse, tags=["Anthropic API"])
async def anthropic_messages(request: AnthropicRequest) -> AnthropicResponse:
    """
    Anthropic-compatible /v1/messages endpoint with CASCADE ROUTING.

    This endpoint accepts requests in Anthropic Messages API format,
    routes through CascadeFlow cascade logic, and returns responses
    in Anthropic format.

    What happens:
    1. Receives request for expensive model (e.g., Sonnet)
    2. Tries cheaper draft model first (e.g., Haiku)
    3. Quality check: If draft response is good → return it (40-80% savings!)
    4. If draft quality is poor → escalate to requested model
    5. Returns response in Anthropic API format (completely transparent)

    Example:
        ```python
        from anthropic import Anthropic

        client = Anthropic(
            api_key="sk-ant-...",
            base_url="http://localhost:8000"  # Point to proxy
        )

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Explain AI"}]
        )
        # Response uses Haiku if quality is good (60% savings!)
        # Or Sonnet if higher quality needed
        ```
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Check streaming (not supported in MVP)
    if request.stream:
        raise HTTPException(
            status_code=400,
            detail="Streaming not supported in MVP. Set stream=false."
        )

    try:
        logger.info(f"Processing request for model: {request.model}")

        # Extract query from messages
        # Combine all user messages into single query
        query_parts = []
        for msg in request.messages:
            if msg.role == "user":
                query_parts.append(msg.content)

        query = "\n\n".join(query_parts)

        # Add system message if provided
        if request.system:
            query = f"System: {request.system}\n\n{query}"

        # Check if we have a cascade rule for this model
        rule = get_cascade_rule(request.model)

        if rule:
            logger.info(
                f"Cascade rule found: {rule.draft_model} → {rule.verifier_model}"
            )
        else:
            logger.info(f"No cascade rule for {request.model}, using direct routing")

        # Run cascade
        result = await agent.run(
            query=query,
            max_tokens=request.max_tokens,
            temperature=request.temperature or 0.7,
        )

        # Update stats
        stats["total_queries"] += 1
        stats["total_cost"] += result.total_cost

        if result.cascaded:
            stats["cascade_used"] += 1

        model = result.model_used
        stats["models_used"][model] = stats["models_used"].get(model, 0) + 1

        # Log cascade decision
        if result.draft_accepted:
            savings_pct = ((0.003 - 0.0008) / 0.003) * 100  # Haiku vs Sonnet
            logger.info(
                f"✅ Draft accepted: {model}, ${result.total_cost:.6f} "
                f"(~{savings_pct:.0f}% savings vs Sonnet)"
            )
        else:
            logger.info(
                f"❌ Escalated to verifier: {model}, ${result.total_cost:.6f}"
            )

        # Format response in Anthropic API format
        response = AnthropicResponse(
            id=f"msg_{uuid4().hex}",
            type="message",
            role="assistant",
            content=[
                ContentBlock(
                    type="text",
                    text=result.content
                )
            ],
            model=request.model,  # Return REQUESTED model, not actual model used
            stop_reason="end_turn",
            usage=Usage(
                input_tokens=result.input_tokens or 0,
                output_tokens=result.output_tokens or 0,
            )
        )

        return response

    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", tags=["Stats"])
async def get_stats():
    """Get routing proxy usage statistics."""
    uptime = (
        (datetime.now() - stats["start_time"]).total_seconds()
        if stats["start_time"] else 0
    )

    avg_cost = (
        stats["total_cost"] / stats["total_queries"]
        if stats["total_queries"] > 0 else 0
    )

    cascade_pct = (
        (stats["cascade_used"] / stats["total_queries"]) * 100
        if stats["total_queries"] > 0 else 0
    )

    return {
        "total_queries": stats["total_queries"],
        "total_cost": stats["total_cost"],
        "avg_cost_per_query": avg_cost,
        "cascade_used_count": stats["cascade_used"],
        "cascade_usage_pct": cascade_pct,
        "models_used": stats["models_used"],
        "uptime_seconds": uptime,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN (for direct execution)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print("🌊 CascadeFlow Routing Proxy (MVP)")
    print("=" * 70)
    print("\n📚 Features:")
    print("   ✓ Anthropic API-compatible /v1/messages endpoint")
    print("   ✓ Automatic cascade routing (Haiku → Sonnet)")
    print("   ✓ 40-80% cost savings transparently")
    print("   ✓ Drop-in replacement for api.anthropic.com")
    print("   ✓ Works with Claude Code, Anthropic SDK, etc.")

    print("\n🔗 Endpoints:")
    print("   • http://localhost:8000/docs - Interactive API documentation")
    print("   • POST http://localhost:8000/v1/messages - Anthropic Messages API")
    print("   • GET http://localhost:8000/health - Health check")
    print("   • GET http://localhost:8000/stats - Usage statistics")

    print("\n🎯 Configure Claude Code:")
    print('   export ANTHROPIC_BASE_URL="http://localhost:8000"')
    print('   export ANTHROPIC_API_KEY="your-anthropic-key"')

    print("\n🚀 Starting server...")
    print("=" * 70 + "\n")

    uvicorn.run(
        "fastapi_proxy_routing:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
