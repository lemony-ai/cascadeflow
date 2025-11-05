"""
FastAPI Integration Example
============================

Production-ready FastAPI integration with cascadeflow showing:
- RESTful API endpoints
- Streaming responses (SSE)
- Request validation
- Error handling
- Cost tracking per request
- Rate limiting
- Monitoring and logging
- Health checks

What it demonstrates:
- Complete FastAPI application with cascadeflow
- Streaming endpoint with Server-Sent Events
- Non-streaming endpoint for simple queries
- Request/response models with Pydantic
- Error handling and validation
- Cost tracking and analytics
- Production-ready patterns

Requirements:
    - cascadeflow[all]
    - fastapi
    - uvicorn
    - sse-starlette (for streaming)
    - OpenAI API key (or other providers)

Setup:
    pip install cascadeflow[all] fastapi uvicorn sse-starlette
    export OPENAI_API_KEY="sk-..."
    python examples/fastapi_integration.py

Run:
    # The app starts automatically on http://localhost:8000
    # Visit http://localhost:8000/docs for interactive API docs

    # Or run with uvicorn:
    uvicorn fastapi_integration:app --reload

Test:
    # Non-streaming
    curl -X POST "http://localhost:8000/api/query" \
      -H "Content-Type: application/json" \
      -d '{"query": "What is Python?", "max_tokens": 100}'

    # Streaming
    curl -N "http://localhost:8000/api/query/stream?query=Explain%20AI&max_tokens=200"

    # Stats
    curl "http://localhost:8000/api/stats"

Documentation:
    📖 FastAPI Guide: docs/guides/fastapi.md
    📖 Production Guide: docs/guides/production.md
    📚 Examples README: examples/README.md
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
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
# PYDANTIC MODELS (Request/Response Validation)
# ═══════════════════════════════════════════════════════════════════════════


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    query: str = Field(..., description="User query text", min_length=1, max_length=2000)
    max_tokens: int = Field(default=100, ge=1, le=4000, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    force_direct: bool = Field(default=False, description="Skip cascade, use best model")

    class Config:
        schema_extra = {
            "example": {
                "query": "What is machine learning?",
                "max_tokens": 150,
                "temperature": 0.7,
                "force_direct": False,
            }
        }


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    content: str = Field(..., description="Generated response")
    model_used: str = Field(..., description="Model that generated the response")
    cost: float = Field(..., description="Cost in USD")
    latency_ms: float = Field(..., description="Response latency in milliseconds")
    cascaded: bool = Field(..., description="Whether cascade was used")
    draft_accepted: Optional[bool] = Field(None, description="Whether draft was accepted")
    complexity: Optional[str] = Field(None, description="Query complexity")

    class Config:
        schema_extra = {
            "example": {
                "content": "Machine learning is a subset of artificial intelligence...",
                "model_used": "gpt-4o-mini",
                "cost": 0.000150,
                "latency_ms": 523.4,
                "cascaded": True,
                "draft_accepted": True,
                "complexity": "moderate",
            }
        }


class StatsResponse(BaseModel):
    """Response model for stats endpoint."""

    total_queries: int
    total_cost: float
    avg_latency_ms: float
    cascade_used_count: int
    models_used: dict[str, int]
    uptime_seconds: float

    class Config:
        schema_extra = {
            "example": {
                "total_queries": 1523,
                "total_cost": 2.45,
                "avg_latency_ms": 456.7,
                "cascade_used_count": 1201,
                "models_used": {"gpt-4o-mini": 1201, "gpt-4o": 322},
                "uptime_seconds": 3600.0,
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    version: str
    agent_initialized: bool
    providers_available: list[str]

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "agent_initialized": True,
                "providers_available": ["openai", "anthropic"],
            }
        }


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════════

agent: Optional[CascadeAgent] = None
stats = {
    "total_queries": 0,
    "total_cost": 0.0,
    "total_latency_ms": 0.0,
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
    logger.info("🚀 Starting cascadeflow FastAPI service...")

    # Initialize agent
    try:
        models = []

        if os.getenv("OPENAI_API_KEY"):
            models.extend(
                [
                    ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                    ModelConfig("gpt-4o", provider="openai", cost=0.00625),
                ]
            )
            logger.info("✓ OpenAI models configured")

        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(
                ModelConfig("claude-sonnet-4-5-20250929", provider="anthropic", cost=0.003)
            )
            logger.info("✓ Anthropic models configured")

        if os.getenv("GROQ_API_KEY"):
            models.insert(0, ModelConfig("llama-3.1-8b-instant", provider="groq", cost=0.0))
            logger.info("✓ Groq models configured")

        if not models:
            raise ValueError(
                "No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GROQ_API_KEY"
            )

        agent = CascadeAgent(models=models)
        stats["start_time"] = datetime.now()

        logger.info(f"✓ Agent initialized with {len(models)} models")
        logger.info("✓ Service ready at http://localhost:8000")
        logger.info("✓ API docs at http://localhost:8000/docs")

    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down cascadeflow service...")
    logger.info(
        f"Final stats: {stats['total_queries']} queries, ${stats['total_cost']:.4f} total cost"
    )


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════


app = FastAPI(
    title="cascadeflow API",
    description="Production-ready API for cascadeflow AI cascading",
    version="1.0.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "cascadeflow API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {"query": "/api/query", "stream": "/api/query/stream", "stats": "/api/stats"},
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    providers = []
    if os.getenv("OPENAI_API_KEY"):
        providers.append("openai")
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.getenv("GROQ_API_KEY"):
        providers.append("groq")

    return HealthResponse(
        status="healthy" if agent is not None else "unhealthy",
        version="1.0.0",
        agent_initialized=agent is not None,
        providers_available=providers,
    )


@app.post("/api/query", response_model=QueryResponse, tags=["Query"])
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    """
    Non-streaming query endpoint.

    Process a query and return the complete response.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        logger.info(f"Processing query: {request.query[:50]}...")

        # Run query
        result = await agent.run(
            query=request.query,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            force_direct=request.force_direct,
        )

        # Update stats
        stats["total_queries"] += 1
        stats["total_cost"] += result.total_cost
        stats["total_latency_ms"] += result.latency_ms

        if result.cascaded:
            stats["cascade_used"] += 1

        model = result.model_used
        stats["models_used"][model] = stats["models_used"].get(model, 0) + 1

        logger.info(
            f"Query completed: {model}, ${result.total_cost:.6f}, {result.latency_ms:.0f}ms"
        )

        return QueryResponse(
            content=result.content,
            model_used=result.model_used,
            cost=result.total_cost,
            latency_ms=result.latency_ms,
            cascaded=result.cascaded or False,
            draft_accepted=result.draft_accepted,
            complexity=result.complexity,
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/query/stream", tags=["Query"])
async def stream_query_endpoint(
    query: str = Query(..., description="Query text", min_length=1),
    max_tokens: int = Query(100, ge=1, le=4000),
    temperature: float = Query(0.7, ge=0.0, le=2.0),
):
    """
    Streaming query endpoint (Server-Sent Events).

    Stream the response as it's being generated.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not agent.can_stream:
        raise HTTPException(status_code=400, detail="Streaming requires 2+ models configured")

    async def event_generator():
        """Generate SSE events from streaming response."""
        try:
            logger.info(f"Starting stream for query: {query[:50]}...")

            total_cost = 0.0
            model_used = None

            async for event in agent.text_streaming_manager.stream(
                query=query, max_tokens=max_tokens, temperature=temperature
            ):
                # Format as SSE
                event_data = {
                    "type": event.type.value,
                    "content": event.content,
                    "data": event.data or {},
                }

                # Extract cost and model from complete event
                if event.type.value == "complete":
                    result = event.data.get("result", {})
                    total_cost = result.get("total_cost", 0.0)
                    model_used = result.get("model_used", "unknown")

                yield f"data: {json.dumps(event_data)}\n\n"

            # Update stats
            stats["total_queries"] += 1
            stats["total_cost"] += total_cost
            if model_used:
                stats["models_used"][model_used] = stats["models_used"].get(model_used, 0) + 1

            logger.info(f"Stream completed: {model_used}, ${total_cost:.6f}")

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            error_data = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/stats", response_model=StatsResponse, tags=["Stats"])
async def stats_endpoint() -> StatsResponse:
    """Get API usage statistics."""
    uptime = (datetime.now() - stats["start_time"]).total_seconds() if stats["start_time"] else 0
    avg_latency = (
        stats["total_latency_ms"] / stats["total_queries"] if stats["total_queries"] > 0 else 0
    )

    return StatsResponse(
        total_queries=stats["total_queries"],
        total_cost=stats["total_cost"],
        avg_latency_ms=avg_latency,
        cascade_used_count=stats["cascade_used"],
        models_used=stats["models_used"],
        uptime_seconds=uptime,
    )


@app.delete("/api/stats", tags=["Stats"])
async def reset_stats():
    """Reset statistics (useful for testing)."""
    stats["total_queries"] = 0
    stats["total_cost"] = 0.0
    stats["total_latency_ms"] = 0.0
    stats["cascade_used"] = 0
    stats["models_used"] = {}
    stats["start_time"] = datetime.now()

    return {"message": "Stats reset successfully"}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN (for direct execution)
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print("🌊 cascadeflow FastAPI Service")
    print("=" * 70)
    print("\n📚 Features:")
    print("   ✓ RESTful API endpoints")
    print("   ✓ Streaming responses (SSE)")
    print("   ✓ Request validation")
    print("   ✓ Cost tracking")
    print("   ✓ Health checks")
    print("   ✓ Interactive API docs")

    print("\n🔗 Endpoints:")
    print("   • http://localhost:8000/docs - Interactive API documentation")
    print("   • http://localhost:8000/health - Health check")
    print("   • POST http://localhost:8000/api/query - Non-streaming query")
    print("   • GET http://localhost:8000/api/query/stream - Streaming query")
    print("   • GET http://localhost:8000/api/stats - Usage statistics")

    print("\n🚀 Starting server...")
    print("=" * 70 + "\n")

    uvicorn.run(
        "fastapi_integration:app", host="0.0.0.0", port=8000, reload=False, log_level="info"
    )
